"""PALM4Umadeeasy – FastAPI application."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
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
from ..db.models import Job, JobStatus, JobType, Project, ScenarioRecord, User
from ..models.scenario import Scenario, ComparisonRequest
from ..validation.engine import validate_scenario
from ..catalogues.loader import load_species, load_surfaces, load_comfort_thresholds
from ..workers.executor import run_job_background, get_job_progress
from .auth import create_access_token, get_password_hash, verify_password
from .deps import get_current_user

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="PALM4Umadeeasy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


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
# Auth routes (/api/auth)
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=get_password_hash(body.password))
    db.add(user)
    await db.flush()
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)


# ---------------------------------------------------------------------------
# Catalogue routes (/api/catalogues)
# ---------------------------------------------------------------------------

@app.get("/api/catalogues/species")
async def get_species_catalogue() -> dict[str, Any]:
    return load_species()


@app.get("/api/catalogues/surfaces")
async def get_surfaces_catalogue() -> dict[str, Any]:
    return load_surfaces()


@app.get("/api/catalogues/comfort-thresholds")
async def get_comfort_thresholds() -> dict[str, Any]:
    return load_comfort_thresholds()


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
    return ProjectResponse(id=project.id, name=project.name, description=project.description)


@app.get("/api/projects", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    stmt = (
        select(Project, func.count(ScenarioRecord.id).label("scenario_count"))
        .outerjoin(ScenarioRecord, ScenarioRecord.project_id == Project.id)
        .where(Project.user_id == user.id)
        .group_by(Project.id)
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
    stmt = (
        select(Project, func.count(ScenarioRecord.id).label("scenario_count"))
        .outerjoin(ScenarioRecord, ScenarioRecord.project_id == Project.id)
        .where(Project.id == project_id, Project.user_id == user.id)
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
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)


# ---------------------------------------------------------------------------
# Scenario routes (/api/projects/{project_id}/scenarios)
# ---------------------------------------------------------------------------

async def _verify_project_access(
    project_id: int, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/projects/{project_id}/scenarios", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    project_id: int,
    body: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    await _verify_project_access(project_id, user, db)
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
    await _verify_project_access(project_id, user, db)
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
    await _verify_project_access(project_id, user, db)
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
    await _verify_project_access(project_id, user, db)
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
    await _verify_project_access(project_id, user, db)
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
    await _verify_project_access(project_id, user, db)
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

    job = Job(
        user_id=user.id,
        project_id=record.project_id,
        job_type=JobType.single,
        baseline_scenario_id=record.id,
        status=JobStatus.pending,
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

    job = Job(
        user_id=user.id,
        project_id=baseline.project_id,
        job_type=JobType.comparison,
        baseline_scenario_id=baseline.id,
        intervention_scenario_id=intervention.id,
        status=JobStatus.pending,
    )
    db.add(job)
    await db.flush()

    run_job_background(job.id)

    return JobResponse(job_id=job.id, status=job.status.value)


@app.get("/api/jobs", response_model=list[dict[str, Any]])
async def list_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())
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
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "error_message": j.error_message,
        }
        for j in jobs
    ]


@app.get("/api/jobs/{job_id}")
async def get_job(
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
    }


@app.get("/api/jobs/{job_id}/results")
async def get_job_results(
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
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
# Export routes (/api/exports)
# ---------------------------------------------------------------------------

@app.get("/api/exports/jobs/{job_id}/pdf")
async def export_pdf(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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
