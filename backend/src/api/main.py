"""PALM4Umadeeasy – FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from rasterio.transform import from_bounds
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import CATALOGUE_DIR, PROJECT_ROOT
from ..db.database import get_db, init_db
from ..db.models import AuditLog, ForcingFile, Job, JobStatus, JobType, Project, ProjectMember, ProjectRole, ScenarioRecord, User
from ..models.scenario import (
    Scenario, ComparisonRequest, BuildingsEdits,
    BuildingEditAdd, BuildingEditModify, BuildingEditRemove,
)
from ..validation.engine import validate_scenario
from ..validation.buildings import (
    validate_buildings_edits,
    resolve_buildings,
    downgraded_buildings_tier,
)
from ..snapshots.buildings import load_snapshot
from ..catalogues.loader import load_species, load_surfaces, load_comfort_thresholds
from ..monitoring.health import get_health
from ..monitoring.metrics import collect_metrics
from ..monitoring.logging_config import setup_logging, generate_request_id, request_id_var
from ..science.forcing_validator import validate_forcing_file
from ..science.facade_greening_advisory import (
    FacadeGreeningInput,
    full_advisory as facade_full_advisory,
    list_supported_species as facade_list_species,
)
from ..science.wind_comfort import generate_stub_wind_comfort, get_category_legend
from ..security.password import validate_password, PasswordValidationError
from ..security.audit import log_action
from ..security.rate_limit import auth_limiter
from ..workers.executor import run_job_background, get_job_progress, ensure_embedded_worker
from .auth import create_access_token, get_password_hash, verify_password
from .deps import get_current_user

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging as _logging
    setup_logging()
    _logger = _logging.getLogger(__name__)

    from .auth import SECRET_KEY
    if SECRET_KEY == "palm4u-dev-secret-change-in-production" and not os.getenv("PALM4U_DEV_MODE", ""):
        _logger.warning(
            "JWT_SECRET_KEY is using the default dev secret. "
            "Set JWT_SECRET_KEY env var for production."
        )

    await init_db()
    ensure_embedded_worker()
    yield


app = FastAPI(title="PALM4Umadeeasy", version="0.1.0", lifespan=lifespan)

from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)


from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next: RequestResponseEndpoint) -> StarletteResponse:
        rid = request.headers.get("X-Request-ID") or generate_request_id()
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    scenario_count: int = 0


class ScenarioCreate(BaseModel):
    scenario_json: dict[str, Any]


class ScenarioResponse(BaseModel):
    id: int
    name: str
    scenario_type: str
    scenario_json: dict[str, Any]


class RunJobRequest(BaseModel):
    scenario_id: int


class CompareJobRequest(BaseModel):
    baseline_id: int
    intervention_id: int
    name: str
    description: str = ""


class JobResponse(BaseModel):
    job_id: int
    status: str


class AddMemberRequest(BaseModel):
    email: str
    role: str = "viewer"


class UpdateMemberRequest(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: int
    user_id: int
    email: str
    role: str


class BBoxInput(BaseModel):
    west: float
    south: float
    east: float
    north: float


class BuildingsRequest(BaseModel):
    bbox: BBoxInput
    epsg: int = 25832


class DEMRequest(BaseModel):
    bbox: BBoxInput
    epsg: int = 25832


# ---------------------------------------------------------------------------
# Health & Metrics (unauthenticated)
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health_endpoint(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_health(db)


@app.get("/api/metrics")
async def metrics_endpoint(db: AsyncSession = Depends(get_db)) -> Response:
    body = await collect_metrics(db)
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# Auth routes (/api/auth)
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(request: StarletteRequest, body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not auth_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    try:
        validate_password(body.password)
    except PasswordValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=get_password_hash(body.password))
    db.add(user)
    await db.flush()
    await log_action(db, user.id, "register", "user", user.id, ip_address=client_ip)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(
    request: StarletteRequest,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not auth_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        await log_action(db, None, "login_failed", "auth", detail=f"email={form.username}", ip_address=client_ip)
        await db.commit()  # Persist audit log before raising
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await log_action(db, user.id, "login", "user", user.id, ip_address=client_ip)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)


# ---------------------------------------------------------------------------
# Catalogue routes (/api/catalogues)
# ---------------------------------------------------------------------------

from starlette.responses import JSONResponse

def _cached_json(data: dict, max_age: int = 3600) -> JSONResponse:
    return JSONResponse(content=data, headers={"Cache-Control": f"public, max-age={max_age}"})


@app.get("/api/catalogues/species")
async def get_species_catalogue() -> JSONResponse:
    return _cached_json(load_species())


@app.get("/api/catalogues/surfaces")
async def get_surfaces_catalogue() -> JSONResponse:
    return _cached_json(load_surfaces())


@app.get("/api/catalogues/comfort-thresholds")
async def get_comfort_thresholds() -> JSONResponse:
    return _cached_json(load_comfort_thresholds())


# ---------------------------------------------------------------------------
# Project routes (/api/projects)
# ---------------------------------------------------------------------------

@app.post("/api/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = Project(name=body.name, description=body.description, user_id=user.id)
    db.add(project)
    await db.flush()
    # Auto-create owner membership
    membership = ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.owner)
    db.add(membership)
    await db.flush()
    return ProjectResponse(id=project.id, name=project.name, description=project.description)


@app.get("/api/projects", response_model=list[ProjectResponse])
async def list_projects(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    # Total count of accessible projects (distinct, since outerjoin can dup)
    count_stmt = (
        select(func.count(func.distinct(Project.id)))
        .outerjoin(ProjectMember, ProjectMember.project_id == Project.id)
        .where((Project.user_id == user.id) | (ProjectMember.user_id == user.id))
    )
    total = (await db.execute(count_stmt)).scalar_one()
    response.headers["X-Total-Count"] = str(total)

    stmt = (
        select(Project, func.count(ScenarioRecord.id).label("scenario_count"))
        .outerjoin(ScenarioRecord, ScenarioRecord.project_id == Project.id)
        .outerjoin(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            (Project.user_id == user.id) | (ProjectMember.user_id == user.id)
        )
        .group_by(Project.id)
        .order_by(Project.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ProjectResponse(
            id=row.Project.id,
            name=row.Project.name,
            description=row.Project.description,
            scenario_count=row.scenario_count,
        )
        for row in rows
    ]


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    stmt = (
        select(Project, func.count(ScenarioRecord.id).label("scenario_count"))
        .outerjoin(ScenarioRecord, ScenarioRecord.project_id == Project.id)
        .where(Project.id == project_id)
        .group_by(Project.id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=row.Project.id,
        name=row.Project.name,
        description=row.Project.description,
        scenario_count=row.scenario_count,
    )


@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_project_access(project_id, user, db, min_role="owner")
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)


# ---------------------------------------------------------------------------
# Project member routes (/api/projects/{project_id}/members)
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY = {"viewer": 0, "editor": 1, "owner": 2}


@app.get("/api/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    result = await db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
    )
    rows = result.all()
    return [
        MemberResponse(
            id=row.ProjectMember.id,
            user_id=row.User.id,
            email=row.User.email,
            role=row.ProjectMember.role.value,
        )
        for row in rows
    ]


@app.post("/api/projects/{project_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    project_id: int,
    body: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    await _verify_project_access(project_id, user, db, min_role="owner")

    if body.role not in ("viewer", "editor"):
        raise HTTPException(status_code=400, detail="Role must be 'viewer' or 'editor'")

    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already a member
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")

    role = ProjectRole(body.role)
    membership = ProjectMember(project_id=project_id, user_id=target_user.id, role=role)
    db.add(membership)
    await db.flush()
    return MemberResponse(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        role=role.value,
    )


@app.put("/api/projects/{project_id}/members/{member_id}", response_model=MemberResponse)
async def update_member(
    project_id: int,
    member_id: int,
    body: UpdateMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    await _verify_project_access(project_id, user, db, min_role="owner")

    if body.role not in ("viewer", "editor"):
        raise HTTPException(status_code=400, detail="Role must be 'viewer' or 'editor'")

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == ProjectRole.owner:
        raise HTTPException(status_code=400, detail="Cannot change owner role")

    membership.role = ProjectRole(body.role)
    await db.flush()

    target = await db.execute(select(User).where(User.id == membership.user_id))
    target_user = target.scalar_one()
    return MemberResponse(
        id=membership.id,
        user_id=target_user.id,
        email=target_user.email,
        role=membership.role.value,
    )


@app.delete("/api/projects/{project_id}/members/{member_id}", status_code=204)
async def remove_member(
    project_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_project_access(project_id, user, db, min_role="owner")

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == ProjectRole.owner:
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")

    await db.delete(membership)


# ---------------------------------------------------------------------------
# Scenario routes (/api/projects/{project_id}/scenarios)
# ---------------------------------------------------------------------------


async def _verify_project_access(
    project_id: int,
    user: User,
    db: AsyncSession,
    min_role: str = "viewer",
) -> ProjectRole:
    """Check user has at least `min_role` on the project. Returns actual role."""
    # Check membership table first
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()

    if member:
        role = member.role
    else:
        # Fallback: legacy owner check (projects created before RBAC)
        proj = await db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user.id)
        )
        if proj.scalar_one_or_none():
            role = ProjectRole.owner
        else:
            raise HTTPException(status_code=404, detail="Project not found")

    if _ROLE_HIERARCHY[role.value] < _ROLE_HIERARCHY[min_role]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return role


@app.post("/api/projects/{project_id}/scenarios", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    project_id: int,
    body: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    await _verify_project_access(project_id, user, db, min_role="editor")
    scenario = Scenario(**body.scenario_json)
    record = ScenarioRecord(
        project_id=project_id,
        name=scenario.name,
        scenario_type=scenario.scenario_type.value,
        scenario_json=scenario.model_dump_json(),
    )
    db.add(record)
    await db.flush()
    return ScenarioResponse(
        id=record.id,
        name=record.name,
        scenario_type=record.scenario_type,
        scenario_json=json.loads(record.scenario_json),
    )


@app.get("/api/projects/{project_id}/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    result = await db.execute(
        select(ScenarioRecord).where(ScenarioRecord.project_id == project_id)
    )
    records = result.scalars().all()
    return [
        ScenarioResponse(
            id=r.id,
            name=r.name,
            scenario_type=r.scenario_type,
            scenario_json=json.loads(r.scenario_json),
        )
        for r in records
    ]


@app.get("/api/projects/{project_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    project_id: int,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    result = await db.execute(
        select(ScenarioRecord).where(
            ScenarioRecord.id == scenario_id,
            ScenarioRecord.project_id == project_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return ScenarioResponse(
        id=record.id,
        name=record.name,
        scenario_type=record.scenario_type,
        scenario_json=json.loads(record.scenario_json),
    )


@app.put("/api/projects/{project_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    project_id: int,
    scenario_id: int,
    body: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    await _verify_project_access(project_id, user, db, min_role="editor")
    result = await db.execute(
        select(ScenarioRecord).where(
            ScenarioRecord.id == scenario_id,
            ScenarioRecord.project_id == project_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario = Scenario(**body.scenario_json)
    record.name = scenario.name
    record.scenario_type = scenario.scenario_type.value
    record.scenario_json = scenario.model_dump_json()
    await db.flush()
    return ScenarioResponse(
        id=record.id,
        name=record.name,
        scenario_type=record.scenario_type,
        scenario_json=json.loads(record.scenario_json),
    )


@app.delete("/api/projects/{project_id}/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(
    project_id: int,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_project_access(project_id, user, db, min_role="editor")
    result = await db.execute(
        select(ScenarioRecord).where(
            ScenarioRecord.id == scenario_id,
            ScenarioRecord.project_id == project_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")
    await db.delete(record)


@app.post("/api/projects/{project_id}/scenarios/{scenario_id}/validate")
async def validate_scenario_endpoint(
    project_id: int,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    result = await db.execute(
        select(ScenarioRecord).where(
            ScenarioRecord.id == scenario_id,
            ScenarioRecord.project_id == project_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario = Scenario(**json.loads(record.scenario_json))
    vr = validate_scenario(scenario)
    return {
        "valid": vr.valid,
        "issues": [
            {"code": i.code, "severity": i.severity.value, "message": i.message, "context": i.context}
            for i in vr.issues
        ],
    }


# ---------------------------------------------------------------------------
# Building geometry edit routes (ADR-004 §7)
# ---------------------------------------------------------------------------

class _EditCreate(BaseModel):
    op: str
    id: str | None = None
    geometry: dict | None = None
    height_m: float | None = None
    roof_type: str | None = None
    wall_material_id: str | None = None
    target_building_id: str | None = None
    set: dict | None = None


def _scenario_record(project_id: int, scenario_id: int, db: AsyncSession):
    return db.execute(
        select(ScenarioRecord).where(
            ScenarioRecord.id == scenario_id,
            ScenarioRecord.project_id == project_id,
        )
    )


async def _load_scenario_or_404(project_id: int, scenario_id: int, db: AsyncSession) -> tuple[ScenarioRecord, Scenario]:
    result = await _scenario_record(project_id, scenario_id, db)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scenario = Scenario(**json.loads(record.scenario_json))
    return record, scenario


def _next_edit_id(scenario: Scenario) -> str:
    existing = (
        {e.id for e in scenario.buildings_edits.edits}
        if scenario.buildings_edits else set()
    )
    n = 1
    while f"e{n}" in existing:
        n += 1
    return f"e{n}"


def _persist_scenario(record: ScenarioRecord, scenario: Scenario) -> None:
    record.scenario_json = scenario.model_dump_json()


def _resolved_payload(scenario: Scenario) -> dict:
    edits_obj = scenario.buildings_edits
    base = load_snapshot(edits_obj.base_snapshot_id) if edits_obj else []
    resolved = resolve_buildings(base, edits_obj)
    return {
        "base_snapshot_id": edits_obj.base_snapshot_id if edits_obj else None,
        "edit_count": len(edits_obj.edits) if edits_obj else 0,
        "buildings": [
            {
                "building_id": rb.building_id,
                "geometry": rb.geometry,
                "height_m": rb.height_m,
                "roof_type": rb.roof_type,
                "wall_material_id": rb.wall_material_id,
                "source": rb.source,
            }
            for rb in resolved
        ],
    }


@app.get("/api/projects/{project_id}/scenarios/{scenario_id}/buildings")
async def get_resolved_buildings(
    project_id: int,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    _, scenario = await _load_scenario_or_404(project_id, scenario_id, db)
    return _resolved_payload(scenario)


@app.post("/api/projects/{project_id}/scenarios/{scenario_id}/buildings/edits", status_code=201)
async def append_building_edit(
    project_id: int,
    scenario_id: int,
    body: _EditCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _verify_project_access(project_id, user, db, min_role="editor")
    record, scenario = await _load_scenario_or_404(project_id, scenario_id, db)

    if scenario.buildings_edits is None:
        raise HTTPException(
            status_code=400,
            detail="scenario.buildings_edits is not initialised; set base_snapshot_id first",
        )

    eid = body.id or _next_edit_id(scenario)
    payload = body.model_dump(exclude_none=True)
    payload["id"] = eid

    try:
        if body.op == "add":
            edit = BuildingEditAdd(**payload)
        elif body.op == "modify":
            edit = BuildingEditModify(**payload)
        elif body.op == "remove":
            edit = BuildingEditRemove(**payload)
        else:
            raise HTTPException(status_code=400, detail=f"unknown op {body.op!r}")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid edit: {exc}")

    new_edits = list(scenario.buildings_edits.edits) + [edit]
    scenario.buildings_edits = BuildingsEdits(
        base_source=scenario.buildings_edits.base_source,
        base_snapshot_id=scenario.buildings_edits.base_snapshot_id,
        edits=new_edits,
    )

    base = load_snapshot(scenario.buildings_edits.base_snapshot_id)
    result = validate_buildings_edits(scenario, base)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "edit chain failed validation",
                "errors": [
                    {"edit_id": e.edit_id, "code": e.code, "message": e.message}
                    for e in result.errors
                ],
            },
        )

    _persist_scenario(record, scenario)
    await db.flush()
    await log_action(db, user.id, "buildings.edit_append", "scenario_buildings", scenario_id, detail=eid)
    return {
        "edit_id": eid,
        "warnings": [
            {"edit_id": w.edit_id, "code": w.code, "message": w.message}
            for w in result.warnings
        ],
        "resolved": _resolved_payload(scenario),
    }


@app.delete(
    "/api/projects/{project_id}/scenarios/{scenario_id}/buildings/edits/{edit_id}",
    status_code=200,
)
async def delete_building_edit(
    project_id: int,
    scenario_id: int,
    edit_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _verify_project_access(project_id, user, db, min_role="editor")
    record, scenario = await _load_scenario_or_404(project_id, scenario_id, db)
    if scenario.buildings_edits is None:
        raise HTTPException(status_code=404, detail="no edits to delete")

    new_edits = [e for e in scenario.buildings_edits.edits if e.id != edit_id]
    if len(new_edits) == len(scenario.buildings_edits.edits):
        raise HTTPException(status_code=404, detail=f"edit {edit_id!r} not found")

    scenario.buildings_edits = BuildingsEdits(
        base_source=scenario.buildings_edits.base_source,
        base_snapshot_id=scenario.buildings_edits.base_snapshot_id,
        edits=new_edits,
    )

    base = load_snapshot(scenario.buildings_edits.base_snapshot_id)
    result = validate_buildings_edits(scenario, base)
    if not result.valid:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "deleting this edit invalidates a later edit; "
                           "remove the dependent edit first",
                "errors": [
                    {"edit_id": e.edit_id, "code": e.code, "message": e.message}
                    for e in result.errors
                ],
            },
        )

    _persist_scenario(record, scenario)
    await db.flush()
    await log_action(db, user.id, "buildings.edit_delete", "scenario_buildings", scenario_id, detail=edit_id)
    return {"deleted": edit_id, "resolved": _resolved_payload(scenario)}


class _ReorderRequest(BaseModel):
    ordered_ids: list[str]


@app.post("/api/projects/{project_id}/scenarios/{scenario_id}/buildings/edits:reorder")
async def reorder_building_edits(
    project_id: int,
    scenario_id: int,
    body: _ReorderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _verify_project_access(project_id, user, db, min_role="editor")
    record, scenario = await _load_scenario_or_404(project_id, scenario_id, db)
    if scenario.buildings_edits is None or not scenario.buildings_edits.edits:
        raise HTTPException(status_code=404, detail="no edits to reorder")

    edits_by_id = {e.id: e for e in scenario.buildings_edits.edits}
    if set(body.ordered_ids) != set(edits_by_id.keys()):
        raise HTTPException(
            status_code=422,
            detail="ordered_ids must contain exactly the same ids as the existing edits",
        )

    reordered = [edits_by_id[i] for i in body.ordered_ids]
    scenario.buildings_edits = BuildingsEdits(
        base_source=scenario.buildings_edits.base_source,
        base_snapshot_id=scenario.buildings_edits.base_snapshot_id,
        edits=reordered,
    )

    base = load_snapshot(scenario.buildings_edits.base_snapshot_id)
    result = validate_buildings_edits(scenario, base)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "the requested order is not valid",
                "errors": [
                    {"edit_id": e.edit_id, "code": e.code, "message": e.message}
                    for e in result.errors
                ],
            },
        )

    _persist_scenario(record, scenario)
    await db.flush()
    await log_action(db, user.id, "buildings.edit_reorder", "scenario_buildings", scenario_id)
    return {"resolved": _resolved_payload(scenario)}


# ---------------------------------------------------------------------------
# Job routes (/api/jobs)
# ---------------------------------------------------------------------------

@app.post("/api/jobs/run", response_model=JobResponse, status_code=202)
async def run_job(
    body: RunJobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    result = await db.execute(select(ScenarioRecord).where(ScenarioRecord.id == body.scenario_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Scenario not found")

    await _verify_project_access(record.project_id, user, db, min_role="editor")

    job = Job(
        user_id=user.id,
        project_id=record.project_id,
        job_type=JobType.single,
        baseline_scenario_id=record.id,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()

    run_job_background(job.id)

    return JobResponse(job_id=job.id, status=job.status.value)


@app.post("/api/jobs/compare", response_model=JobResponse, status_code=202)
async def compare_job(
    body: CompareJobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    baseline = (await db.execute(
        select(ScenarioRecord).where(ScenarioRecord.id == body.baseline_id)
    )).scalar_one_or_none()
    intervention = (await db.execute(
        select(ScenarioRecord).where(ScenarioRecord.id == body.intervention_id)
    )).scalar_one_or_none()

    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline scenario not found")
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention scenario not found")
    if baseline.project_id != intervention.project_id:
        raise HTTPException(status_code=400, detail="Scenarios must belong to the same project")

    await _verify_project_access(baseline.project_id, user, db, min_role="editor")

    job = Job(
        user_id=user.id,
        project_id=baseline.project_id,
        job_type=JobType.comparison,
        baseline_scenario_id=baseline.id,
        intervention_scenario_id=intervention.id,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()

    run_job_background(job.id)

    return JobResponse(job_id=job.id, status=job.status.value)


@app.get("/api/jobs", response_model=list[dict[str, Any]])
async def list_jobs(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    base = (
        select(Job)
        .outerjoin(ProjectMember, (ProjectMember.project_id == Job.project_id) & (ProjectMember.user_id == user.id))
        .where((Job.user_id == user.id) | (ProjectMember.user_id == user.id))
    )
    if status_filter:
        try:
            base = base.where(Job.status == JobStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"invalid status: {status_filter}")

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    response.headers["X-Total-Count"] = str(total)

    result = await db.execute(
        base.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "job_id": j.id,
            "job_type": j.job_type.value,
            "status": j.status.value,
            "project_id": j.project_id,
            "baseline_scenario_id": j.baseline_scenario_id,
            "intervention_scenario_id": j.intervention_scenario_id,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "error_message": j.error_message,
            "worker_id": j.worker_id,
            "retry_count": j.retry_count,
            "priority": j.priority,
        }
        for j in jobs
    ]


@app.get("/api/jobs/{job_id}")
async def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")

    summary = json.loads(job.result_json) if job.result_json else None
    return {
        "job_id": job.id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "project_id": job.project_id,
        "baseline_scenario_id": job.baseline_scenario_id,
        "intervention_scenario_id": job.intervention_scenario_id,
        "output_dir": job.output_dir,
        "result_summary": summary,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "worker_id": job.worker_id,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "priority": job.priority,
    }


@app.get("/api/jobs/{job_id}/results")
async def get_job_results(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Job has not completed")
    if not job.result_json:
        raise HTTPException(status_code=404, detail="No results available")

    return json.loads(job.result_json)


@app.get("/api/jobs/{job_id}/results/field/{variable}/{timestep}")
async def get_field_geotiff(
    job_id: int,
    variable: str,
    timestep: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Job has not completed")
    if not job.output_dir:
        raise HTTPException(status_code=404, detail="No output directory")

    import xarray as xr

    output_path = Path(job.output_dir)
    nc_files = list(output_path.glob("*_3d.nc")) + list(output_path.glob("*_av.nc"))
    if not nc_files:
        raise HTTPException(status_code=404, detail="No NetCDF output files found")

    ds = xr.open_dataset(nc_files[0])
    if variable not in ds.data_vars:
        raise HTTPException(
            status_code=404,
            detail=f"Variable '{variable}' not found. Available: {list(ds.data_vars)}",
        )

    var_data = ds[variable]
    if "time" in var_data.dims:
        if timestep >= var_data.sizes["time"]:
            raise HTTPException(status_code=400, detail=f"Timestep {timestep} out of range")
        var_data = var_data.isel(time=timestep)
    if "z" in var_data.dims:
        var_data = var_data.isel(z=0)

    data_2d = var_data.values.astype(np.float32)
    ny, nx = data_2d.shape

    result_meta = json.loads(job.result_json) if job.result_json else {}
    west = result_meta.get("domain", {}).get("west", 0.0)
    south = result_meta.get("domain", {}).get("south", 0.0)
    east = result_meta.get("domain", {}).get("east", west + nx)
    north = result_meta.get("domain", {}).get("north", south + ny)
    epsg = result_meta.get("domain", {}).get("epsg", 25832)

    transform = from_bounds(west, south, east, north, nx, ny)

    buf = BytesIO()
    with rasterio.open(
        buf,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=transform,
    ) as dst:
        dst.write(data_2d, 1)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="image/tiff",
        headers={"Content-Disposition": f"attachment; filename={variable}_t{timestep}.tif"},
    )


@app.get("/api/jobs/{job_id}/comparison")
async def get_comparison_results(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.job_type != JobType.comparison:
        raise HTTPException(status_code=400, detail="Job is not a comparison job")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Job has not completed")
    if not job.result_json:
        raise HTTPException(status_code=404, detail="No results available")

    return json.loads(job.result_json)


# ---------------------------------------------------------------------------
# Job retry / cancel
# ---------------------------------------------------------------------------


@app.get("/api/jobs/{job_id}/wind-comfort")
async def get_wind_comfort(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Job has not completed")

    # In stub mode, generate synthetic wind comfort data
    return generate_stub_wind_comfort()


@app.get("/api/catalogues/wind-comfort-legend")
async def wind_comfort_legend() -> list[dict]:
    return get_category_legend()


@app.post("/api/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="editor")

    if job.status not in (JobStatus.failed, JobStatus.cancelled):
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")

    job.status = JobStatus.queued
    job.worker_id = None
    job.last_heartbeat = None
    job.started_at = None
    job.completed_at = None
    job.error_message = None
    job.retry_count = 0
    await db.flush()

    run_job_background(job.id)

    return JobResponse(job_id=job.id, status=job.status.value)


@app.post("/api/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="editor")

    if job.status != JobStatus.queued:
        raise HTTPException(status_code=400, detail="Only queued jobs can be cancelled")

    from datetime import datetime, timezone
    job.status = JobStatus.cancelled
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JobResponse(job_id=job.id, status=job.status.value)


# ---------------------------------------------------------------------------
# Export routes (/api/exports)
# ---------------------------------------------------------------------------

@app.get("/api/exports/jobs/{job_id}/pdf")
async def export_pdf(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")
    if not job.output_dir:
        raise HTTPException(status_code=404, detail="No output directory")

    output_path = Path(job.output_dir)
    pdf_files = list(output_path.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF report not found")

    pdf_bytes = pdf_files[0].read_bytes()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_job_{job_id}.pdf"},
    )


@app.get("/api/exports/jobs/{job_id}/geotiff/{variable}")
async def export_geotiff(
    job_id: int,
    variable: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await _verify_project_access(job.project_id, user, db, min_role="viewer")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Job has not completed")
    if not job.output_dir:
        raise HTTPException(status_code=404, detail="No output directory")

    import xarray as xr

    output_path = Path(job.output_dir)
    nc_files = list(output_path.glob("*_3d.nc")) + list(output_path.glob("*_av.nc"))
    if not nc_files:
        raise HTTPException(status_code=404, detail="No NetCDF output files found")

    ds = xr.open_dataset(nc_files[0])
    if variable not in ds.data_vars:
        raise HTTPException(
            status_code=404,
            detail=f"Variable '{variable}' not found. Available: {list(ds.data_vars)}",
        )

    var_data = ds[variable]
    if "z" in var_data.dims:
        var_data = var_data.isel(z=0)
    if "time" in var_data.dims:
        var_data = var_data.mean(dim="time")

    data_2d = var_data.values.astype(np.float32)
    ny, nx = data_2d.shape

    result_meta = json.loads(job.result_json) if job.result_json else {}
    west = result_meta.get("domain", {}).get("west", 0.0)
    south = result_meta.get("domain", {}).get("south", 0.0)
    east = result_meta.get("domain", {}).get("east", west + nx)
    north = result_meta.get("domain", {}).get("north", south + ny)
    epsg = result_meta.get("domain", {}).get("epsg", 25832)

    transform = from_bounds(west, south, east, north, nx, ny)

    buf = BytesIO()
    with rasterio.open(
        buf,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=transform,
    ) as dst:
        dst.write(data_2d, 1)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="image/tiff",
        headers={"Content-Disposition": f"attachment; filename={variable}_avg_job_{job_id}.tif"},
    )


# ---------------------------------------------------------------------------
# Data fetch routes (/api/data)
# ---------------------------------------------------------------------------

@app.post("/api/data/buildings")
async def fetch_buildings(body: BuildingsRequest) -> dict[str, Any]:
    south, west = body.bbox.south, body.bbox.west
    north, east = body.bbox.north, body.bbox.east

    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""[out:json][timeout:30];
(way["building"]({south},{west},{north},{east}););
out body;>;out skel qt;"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(overpass_url, data={"data": query})
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Overpass API request failed")
        data = resp.json()

    nodes: dict[int, dict[str, float]] = {}
    ways: list[dict[str, Any]] = []

    for element in data.get("elements", []):
        if element["type"] == "node":
            nodes[element["id"]] = {"lat": element["lat"], "lon": element["lon"]}
        elif element["type"] == "way":
            ways.append(element)

    features: list[dict[str, Any]] = []
    for way in ways:
        coords = []
        for node_id in way.get("nodes", []):
            node = nodes.get(node_id)
            if node:
                coords.append([node["lon"], node["lat"]])
        if len(coords) < 4:
            continue

        tags = way.get("tags", {})
        height: float | None = None
        raw_height = tags.get("height") or tags.get("building:height")
        if raw_height:
            try:
                height = float(str(raw_height).replace("m", "").strip())
            except ValueError:
                pass
        levels = tags.get("building:levels")
        if height is None and levels:
            try:
                height = float(levels) * 3.0
            except ValueError:
                pass

        properties: dict[str, Any] = {
            "osm_id": way["id"],
            "building": tags.get("building", "yes"),
            "height": height,
            "levels": levels,
        }

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": properties,
        })

    total = len(features)
    with_height = sum(1 for f in features if f["properties"]["height"] is not None)

    return {
        "type": "FeatureCollection",
        "features": features,
        "quality": {
            "total_buildings": total,
            "with_height": with_height,
            "height_coverage_pct": round(with_height / total * 100, 1) if total else 0.0,
            "source": "OpenStreetMap via Overpass API",
        },
    }


@app.post("/api/data/dem")
async def fetch_dem(body: DEMRequest) -> dict[str, Any]:
    width_m = abs(body.bbox.east - body.bbox.west)
    height_m = abs(body.bbox.north - body.bbox.south)
    return {
        "status": "stub",
        "message": "DEM fetch deferred to execution phase. Screening-tier flat terrain assumed.",
        "bbox": {
            "west": body.bbox.west,
            "south": body.bbox.south,
            "east": body.bbox.east,
            "north": body.bbox.north,
        },
        "epsg": body.epsg,
        "estimated_extent_m": {"width": round(width_m, 1), "height": round(height_m, 1)},
        "default_elevation_m": 0.0,
        "source": "Copernicus GLO-30 DEM (deferred)",
    }


# ---------------------------------------------------------------------------
# Forcing file routes (/api/projects/{project_id}/forcing)
# ---------------------------------------------------------------------------

FORCING_UPLOAD_DIR = Path(os.getenv("PALM4U_FORCING_DIR", "./forcing_uploads"))


@app.post("/api/projects/{project_id}/forcing", status_code=201)
async def upload_forcing(
    project_id: int,
    file: UploadFile = File(...),
    description: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _verify_project_access(project_id, user, db, min_role="editor")

    FORCING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"proj{project_id}_{file.filename}"
    dest = FORCING_UPLOAD_DIR / safe_name

    content = await file.read()
    dest.write_bytes(content)

    errors = validate_forcing_file(dest, file.filename or "unknown")

    record = ForcingFile(
        project_id=project_id,
        user_id=user.id,
        filename=safe_name,
        original_name=file.filename or "unknown",
        file_size=len(content),
        description=description,
        validated=len(errors) == 0,
        validation_errors="; ".join(errors) if errors else None,
    )
    db.add(record)
    await db.flush()

    return {
        "id": record.id,
        "filename": record.original_name,
        "file_size": record.file_size,
        "validated": record.validated,
        "validation_errors": errors,
    }


@app.get("/api/projects/{project_id}/forcing")
async def list_forcing(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _verify_project_access(project_id, user, db, min_role="viewer")
    result = await db.execute(
        select(ForcingFile).where(ForcingFile.project_id == project_id).order_by(ForcingFile.created_at.desc())
    )
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.original_name,
            "file_size": f.file_size,
            "validated": f.validated,
            "validation_errors": f.validation_errors,
            "description": f.description,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@app.delete("/api/projects/{project_id}/forcing/{forcing_id}", status_code=204)
async def delete_forcing(
    project_id: int,
    forcing_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_project_access(project_id, user, db, min_role="editor")
    result = await db.execute(
        select(ForcingFile).where(ForcingFile.id == forcing_id, ForcingFile.project_id == project_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Forcing file not found")

    # Delete file from disk
    file_path = FORCING_UPLOAD_DIR / record.filename
    if file_path.exists():
        file_path.unlink()

    await db.delete(record)


# ---------------------------------------------------------------------------
# Facade greening ADVISORY routes (NON-PALM, NON-COUPLED)
#
# IMPORTANT: All responses here carry result_kind="advisory_non_palm" and
# coupled_with_palm=False. They MUST NOT be merged with PALM/PALM-4U
# results in any client, report, or downstream aggregation.
# ---------------------------------------------------------------------------


class FacadeGreeningRequest(BaseModel):
    facade_area_m2: float
    species: str = "hedera_helix"
    coverage_fraction: float = 1.0
    climate_zone: str = "temperate"


@app.post("/api/advisory/facade-greening")
async def advisory_facade_greening(
    body: FacadeGreeningRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """First-order, literature-based facade greening advisory.

    NOT a PALM simulation. Response carries provenance flags that
    downstream consumers must preserve.
    """
    try:
        inp = FacadeGreeningInput(
            facade_area_m2=body.facade_area_m2,
            species=body.species,  # type: ignore[arg-type]
            coverage_fraction=body.coverage_fraction,
            climate_zone=body.climate_zone,
        )
        return facade_full_advisory(inp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/advisory/facade-greening/species")
async def advisory_facade_greening_species(
    user: User = Depends(get_current_user),
) -> dict:
    return {
        "result_kind": "advisory_non_palm",
        "coupled_with_palm": False,
        "species": facade_list_species(),
    }


# ---------------------------------------------------------------------------
# Admin routes (/api/admin) — requires is_admin flag
# ---------------------------------------------------------------------------


async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@app.get("/api/admin/queue-stats")
async def admin_queue_stats(
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    )
    counts = {row[0].value: row[1] for row in result.all()}

    # Stale workers
    from datetime import datetime as dt, timezone as tz, timedelta as td
    cutoff = dt.now(tz.utc) - td(seconds=120)
    stale = await db.execute(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.running,
            Job.last_heartbeat < cutoff,
        )
    )
    stale_count = stale.scalar() or 0

    # Active workers
    active = await db.execute(
        select(func.count(func.distinct(Job.worker_id))).where(
            Job.status == JobStatus.running,
            Job.worker_id.isnot(None),
        )
    )
    active_count = active.scalar() or 0

    return {
        "jobs": counts,
        "stale_workers": stale_count,
        "active_workers": active_count,
    }


@app.get("/api/admin/audit-log")
async def admin_audit_log(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    response.headers["X-Total-Count"] = str(total)

    stmt = base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "request_id": log.request_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@app.get("/api/admin/users")
async def admin_list_users(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    rows = (
        await db.execute(
            select(User).order_by(User.id.asc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]


class AdminUserPatch(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None


@app.patch("/api/admin/users/{user_id}")
async def admin_patch_user(
    user_id: int,
    body: AdminUserPatch,
    request: Request,
    actor: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id and body.is_active is False:
        raise HTTPException(status_code=400, detail="Admins cannot deactivate themselves")
    if target.id == actor.id and body.is_admin is False:
        raise HTTPException(status_code=400, detail="Admins cannot demote themselves")

    changes = {}
    if body.is_admin is not None and body.is_admin != target.is_admin:
        target.is_admin = body.is_admin
        changes["is_admin"] = body.is_admin
    if body.is_active is not None and body.is_active != target.is_active:
        target.is_active = body.is_active
        changes["is_active"] = body.is_active

    if changes:
        await log_action(
            db,
            user_id=actor.id,
            action="admin_user_patch",
            resource_type="user",
            resource_id=str(target.id),
            detail=str(changes),
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

    return {
        "id": target.id,
        "email": target.email,
        "is_admin": target.is_admin,
        "is_active": target.is_active,
    }


@app.get("/api/admin/jobs")
async def admin_list_jobs(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    actor: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """System-wide job view (all users, all projects)."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    base = select(Job)
    if status_filter:
        try:
            base = base.where(Job.status == JobStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"invalid status: {status_filter}")
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    rows = (
        await db.execute(
            base.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "job_id": j.id,
            "user_id": j.user_id,
            "project_id": j.project_id,
            "job_type": j.job_type.value,
            "status": j.status.value,
            "worker_id": j.worker_id,
            "priority": j.priority,
            "retry_count": j.retry_count,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "error_message": j.error_message,
        }
        for j in rows
    ]


# ---------------------------------------------------------------------------
# WebSocket (/api/ws/jobs/{job_id})
# ---------------------------------------------------------------------------

@app.websocket("/api/ws/jobs/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: int) -> None:
    await websocket.accept()
    try:
        while True:
            progress = get_job_progress(job_id)
            await websocket.send_json(progress)
            if progress.get("status") in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
