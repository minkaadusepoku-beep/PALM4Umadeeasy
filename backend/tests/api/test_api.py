"""API integration tests for PALM4Umadeeasy FastAPI endpoints."""

from __future__ import annotations

import json
import os
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override DB URL before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["PALM4U_EXTERNAL_WORKERS"] = "1"  # Disable embedded worker in tests
os.environ["PALM4U_AUTH_RATE_LIMIT"] = "10000"  # Disable rate limiting in tests

from src.db.database import Base, get_db  # noqa: E402
from src.api.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Test DB fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    test_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with test_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Valid scenario JSON fixture
# ---------------------------------------------------------------------------

VALID_SCENARIO_JSON = {
    "name": "Test Baseline",
    "scenario_type": "baseline",
    "domain": {
        "bbox": {
            "west": 356000,
            "south": 5645000,
            "east": 356500,
            "north": 5645500,
        },
        "resolution_m": 10.0,
        "epsg": 25832,
        "nz": 40,
        "dz": 2.0,
    },
    "simulation": {
        "forcing": "typical_hot_day",
        "simulation_hours": 6.0,
        "output_interval_s": 1800.0,
    },
}

VALID_INTERVENTION_JSON = {
    **VALID_SCENARIO_JSON,
    "name": "Test Intervention",
    "scenario_type": "single_intervention",
    "trees": [
        {"species_id": "tilia_cordata", "x": 356250, "y": 5645250},
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_get_token(client: AsyncClient, email: str = "test@example.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Test1234"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestAuth:

    @pytest.mark.asyncio
    async def test_register(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "Test1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "Test1234"},
        )
        resp = await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "Test1234"},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "login@example.com", "password": "Test1234"},
        )
        resp = await client.post(
            "/api/auth/login",
            data={"username": "login@example.com", "password": "Test1234"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "wrong@example.com", "password": "Test1234"},
        )
        resp = await client.post(
            "/api/auth/login",
            data={"username": "wrong@example.com", "password": "Wrong1234"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me(self, client):
        token = await register_and_get_token(client)
        resp = await client.get("/api/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_unauthorized(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self, client):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Catalogue tests
# ---------------------------------------------------------------------------


class TestCatalogues:

    @pytest.mark.asyncio
    async def test_species(self, client):
        resp = await client.get("/api/catalogues/species")
        assert resp.status_code == 200
        data = resp.json()
        assert "tilia_cordata" in data

    @pytest.mark.asyncio
    async def test_surfaces(self, client):
        resp = await client.get("/api/catalogues/surfaces")
        assert resp.status_code == 200
        data = resp.json()
        assert "grass" in data

    @pytest.mark.asyncio
    async def test_comfort_thresholds(self, client):
        resp = await client.get("/api/catalogues/comfort-thresholds")
        assert resp.status_code == 200
        data = resp.json()
        assert "pet_vdi3787" in data


# ---------------------------------------------------------------------------
# Project tests
# ---------------------------------------------------------------------------


class TestProjects:

    @pytest.mark.asyncio
    async def test_create_project(self, client):
        token = await register_and_get_token(client)
        resp = await client.post(
            "/api/projects",
            json={"name": "My Project", "description": "Test project"},
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Project"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_list_projects(self, client):
        token = await register_and_get_token(client)
        await client.post(
            "/api/projects",
            json={"name": "Proj 1"},
            headers=auth_header(token),
        )
        await client.post(
            "/api/projects",
            json={"name": "Proj 2"},
            headers=auth_header(token),
        )
        resp = await client.get("/api/projects", headers=auth_header(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_project(self, client):
        token = await register_and_get_token(client)
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Get Me"},
            headers=auth_header(token),
        )
        pid = create_resp.json()["id"]
        resp = await client.get(f"/api/projects/{pid}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client):
        token = await register_and_get_token(client)
        resp = await client.get("/api/projects/9999", headers=auth_header(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, client):
        token = await register_and_get_token(client)
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Delete Me"},
            headers=auth_header(token),
        )
        pid = create_resp.json()["id"]
        resp = await client.delete(f"/api/projects/{pid}", headers=auth_header(token))
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_projects_isolated_per_user(self, client):
        # User A
        resp_a = await client.post(
            "/api/auth/register",
            json={"email": "a@test.com", "password": "Test1234"},
        )
        token_a = resp_a.json()["access_token"]
        await client.post(
            "/api/projects",
            json={"name": "A's project"},
            headers=auth_header(token_a),
        )

        # User B
        resp_b = await client.post(
            "/api/auth/register",
            json={"email": "b@test.com", "password": "Test1234"},
        )
        token_b = resp_b.json()["access_token"]

        resp = await client.get("/api/projects", headers=auth_header(token_b))
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------


class TestScenarios:

    @pytest.mark.asyncio
    async def test_create_scenario(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]

        resp = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Baseline"
        assert data["scenario_type"] == "baseline"

    @pytest.mark.asyncio
    async def test_list_scenarios(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]

        await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        resp = await client.get(
            f"/api/projects/{pid}/scenarios", headers=auth_header(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_update_scenario(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]
        sc = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        sid = sc.json()["id"]

        updated = {**VALID_SCENARIO_JSON, "name": "Renamed"}
        resp = await client.put(
            f"/api/projects/{pid}/scenarios/{sid}",
            json={"scenario_json": updated},
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_delete_scenario(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]
        sc = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        sid = sc.json()["id"]

        resp = await client.delete(
            f"/api/projects/{pid}/scenarios/{sid}", headers=auth_header(token)
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_validate_scenario(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]
        sc = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        sid = sc.json()["id"]

        resp = await client.post(
            f"/api/projects/{pid}/scenarios/{sid}/validate",
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "issues" in data

    @pytest.mark.asyncio
    async def test_scenario_not_found(self, client):
        token = await register_and_get_token(client)
        proj = await client.post(
            "/api/projects", json={"name": "P"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]

        resp = await client.get(
            f"/api/projects/{pid}/scenarios/9999", headers=auth_header(token)
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Job tests
# ---------------------------------------------------------------------------


class TestJobs:

    async def _create_scenario(self, client, token, scenario_json=None):
        """Helper: create project + scenario, return (project_id, scenario_id)."""
        proj = await client.post(
            "/api/projects", json={"name": "Job Test"}, headers=auth_header(token)
        )
        pid = proj.json()["id"]
        sc = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": scenario_json or VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        return pid, sc.json()["id"]

    @pytest.mark.asyncio
    async def test_run_single_job(self, client):
        token = await register_and_get_token(client)
        _, sid = await self._create_scenario(client, token)

        resp = await client.post(
            "/api/jobs/run",
            json={"scenario_id": sid},
            headers=auth_header(token),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        assert data["job_id"] > 0

    @pytest.mark.asyncio
    async def test_run_comparison_job(self, client):
        token = await register_and_get_token(client)
        _, baseline_id = await self._create_scenario(client, token)
        proj = await client.get("/api/projects", headers=auth_header(token))
        pid = proj.json()[0]["id"]
        sc2 = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_INTERVENTION_JSON},
            headers=auth_header(token),
        )
        intervention_id = sc2.json()["id"]

        resp = await client.post(
            "/api/jobs/compare",
            json={
                "baseline_id": baseline_id,
                "intervention_id": intervention_id,
                "name": "Test Comparison",
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_list_jobs(self, client):
        token = await register_and_get_token(client)
        _, sid = await self._create_scenario(client, token)
        await client.post(
            "/api/jobs/run",
            json={"scenario_id": sid},
            headers=auth_header(token),
        )

        resp = await client.get("/api/jobs", headers=auth_header(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_get_job(self, client):
        token = await register_and_get_token(client)
        _, sid = await self._create_scenario(client, token)
        run_resp = await client.post(
            "/api/jobs/run",
            json={"scenario_id": sid},
            headers=auth_header(token),
        )
        job_id = run_resp.json()["job_id"]

        resp = await client.get(f"/api/jobs/{job_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_job_not_found(self, client):
        token = await register_and_get_token(client)
        resp = await client.get("/api/jobs/9999", headers=auth_header(token))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_job_results_not_ready(self, client):
        token = await register_and_get_token(client)
        _, sid = await self._create_scenario(client, token)
        run_resp = await client.post(
            "/api/jobs/run",
            json={"scenario_id": sid},
            headers=auth_header(token),
        )
        job_id = run_resp.json()["job_id"]

        # Job is pending/running, results should be 409
        resp = await client.get(
            f"/api/jobs/{job_id}/results", headers=auth_header(token)
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_run_scenario_not_found(self, client):
        token = await register_and_get_token(client)
        resp = await client.post(
            "/api/jobs/run",
            json={"scenario_id": 9999},
            headers=auth_header(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Job queue operations tests
# ---------------------------------------------------------------------------


class TestJobQueue:

    async def _create_job(self, client, token):
        """Helper: register, create project+scenario, run job, return (token, job_id)."""
        proj = await client.post(
            "/api/projects",
            json={"name": "Queue Test", "description": "test"},
            headers=auth_header(token),
        )
        pid = proj.json()["id"]
        sc = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=auth_header(token),
        )
        sid = sc.json()["id"]
        run_resp = await client.post(
            "/api/jobs/run",
            json={"scenario_id": sid},
            headers=auth_header(token),
        )
        return run_resp.json()["job_id"]

    @pytest.mark.asyncio
    async def test_cancel_queued_job(self, client):
        token = await register_and_get_token(client, "cancel1@test.com")
        job_id = await self._create_job(client, token)

        resp = await client.post(f"/api/jobs/{job_id}/cancel", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_non_queued_fails(self, client):
        token = await register_and_get_token(client, "cancel2@test.com")
        job_id = await self._create_job(client, token)

        # Cancel it first
        await client.post(f"/api/jobs/{job_id}/cancel", headers=auth_header(token))

        # Try to cancel again (now cancelled, not queued)
        resp = await client.post(f"/api/jobs/{job_id}/cancel", headers=auth_header(token))
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_cancelled_job(self, client):
        token = await register_and_get_token(client, "retry1@test.com")
        job_id = await self._create_job(client, token)

        # Cancel then retry
        await client.post(f"/api/jobs/{job_id}/cancel", headers=auth_header(token))
        resp = await client.post(f"/api/jobs/{job_id}/retry", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    @pytest.mark.asyncio
    async def test_retry_queued_job_fails(self, client):
        token = await register_and_get_token(client, "retry2@test.com")
        job_id = await self._create_job(client, token)

        # Job is queued, retry should fail
        resp = await client.post(f"/api/jobs/{job_id}/retry", headers=auth_header(token))
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_job_includes_queue_fields(self, client):
        token = await register_and_get_token(client, "qfields@test.com")
        job_id = await self._create_job(client, token)

        resp = await client.get(f"/api/jobs/{job_id}", headers=auth_header(token))
        data = resp.json()
        assert "worker_id" in data
        assert "retry_count" in data
        assert "max_retries" in data
        assert "priority" in data
        assert data["retry_count"] == 0
        assert data["priority"] == 0

    @pytest.mark.asyncio
    async def test_viewer_cannot_cancel(self, client):
        owner_token = await register_and_get_token(client, "qown@test.com")
        viewer_token = await register_and_get_token(client, "qview@test.com")
        job_id = await self._create_job(client, owner_token)

        # Add viewer to project
        jobs_resp = await client.get(f"/api/jobs/{job_id}", headers=auth_header(owner_token))
        pid = jobs_resp.json()["project_id"]
        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "qview@test.com", "role": "viewer"},
            headers=auth_header(owner_token),
        )

        # Viewer tries to cancel
        resp = await client.post(f"/api/jobs/{job_id}/cancel", headers=auth_header(viewer_token))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Data fetch tests
# ---------------------------------------------------------------------------


class TestData:

    @pytest.mark.asyncio
    async def test_dem_stub(self, client):
        token = await register_and_get_token(client)
        resp = await client.post(
            "/api/data/dem",
            json={
                "bbox": {"west": 356000, "south": 5645000, "east": 356500, "north": 5645500},
                "epsg": 25832,
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stub"
        assert "Copernicus" in data["source"]


# ---------------------------------------------------------------------------
# Export tests (no completed job → 404/409)
# ---------------------------------------------------------------------------


class TestExports:

    @pytest.mark.asyncio
    async def test_pdf_no_job(self, client):
        token = await register_and_get_token(client)
        resp = await client.get(
            "/api/exports/jobs/9999/pdf", headers=auth_header(token)
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_geotiff_no_job(self, client):
        token = await register_and_get_token(client)
        resp = await client.get(
            "/api/exports/jobs/9999/geotiff/theta", headers=auth_header(token)
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------


async def register_user(client: AsyncClient, email: str, password: str = "Test1234") -> str:
    resp = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestRBAC:

    @pytest.mark.asyncio
    async def test_owner_auto_membership(self, client):
        """Creating a project auto-creates owner membership."""
        token = await register_user(client, "owner@test.com")
        h = auth_header(token)
        resp = await client.post("/api/projects", json={"name": "RBAC Test"}, headers=h)
        assert resp.status_code == 201
        pid = resp.json()["id"]

        members = await client.get(f"/api/projects/{pid}/members", headers=h)
        assert members.status_code == 200
        data = members.json()
        assert len(data) == 1
        assert data[0]["email"] == "owner@test.com"
        assert data[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_add_viewer_member(self, client):
        """Owner can add a viewer to the project."""
        owner_token = await register_user(client, "owner2@test.com")
        viewer_token = await register_user(client, "viewer@test.com")
        oh = auth_header(owner_token)
        vh = auth_header(viewer_token)

        resp = await client.post("/api/projects", json={"name": "Shared"}, headers=oh)
        pid = resp.json()["id"]

        # Add viewer
        add = await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "viewer@test.com", "role": "viewer"},
            headers=oh,
        )
        assert add.status_code == 201
        assert add.json()["role"] == "viewer"

        # Viewer can see the project
        proj = await client.get(f"/api/projects/{pid}", headers=vh)
        assert proj.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_scenario(self, client):
        """Viewer cannot create scenarios (requires editor)."""
        owner_token = await register_user(client, "own3@test.com")
        viewer_token = await register_user(client, "view3@test.com")
        oh = auth_header(owner_token)
        vh = auth_header(viewer_token)

        resp = await client.post("/api/projects", json={"name": "ReadOnly"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "view3@test.com", "role": "viewer"},
            headers=oh,
        )

        # Viewer tries to create scenario
        create = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=vh,
        )
        assert create.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_create_scenario(self, client):
        """Editor can create scenarios."""
        owner_token = await register_user(client, "own4@test.com")
        editor_token = await register_user(client, "edit4@test.com")
        oh = auth_header(owner_token)
        eh = auth_header(editor_token)

        resp = await client.post("/api/projects", json={"name": "Editable"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "edit4@test.com", "role": "editor"},
            headers=oh,
        )

        create = await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=eh,
        )
        assert create.status_code == 201

    @pytest.mark.asyncio
    async def test_viewer_can_list_scenarios(self, client):
        """Viewer can read scenarios."""
        owner_token = await register_user(client, "own5@test.com")
        viewer_token = await register_user(client, "view5@test.com")
        oh = auth_header(owner_token)
        vh = auth_header(viewer_token)

        resp = await client.post("/api/projects", json={"name": "ViewScens"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "view5@test.com", "role": "viewer"},
            headers=oh,
        )

        # Owner creates a scenario
        await client.post(
            f"/api/projects/{pid}/scenarios",
            json={"scenario_json": VALID_SCENARIO_JSON},
            headers=oh,
        )

        # Viewer can list
        scens = await client.get(f"/api/projects/{pid}/scenarios", headers=vh)
        assert scens.status_code == 200
        assert len(scens.json()) == 1

    @pytest.mark.asyncio
    async def test_non_member_cannot_access(self, client):
        """User with no membership gets 404."""
        owner_token = await register_user(client, "own6@test.com")
        outsider_token = await register_user(client, "outsider6@test.com")
        oh = auth_header(owner_token)
        xh = auth_header(outsider_token)

        resp = await client.post("/api/projects", json={"name": "Private"}, headers=oh)
        pid = resp.json()["id"]

        get = await client.get(f"/api/projects/{pid}", headers=xh)
        assert get.status_code == 404

    @pytest.mark.asyncio
    async def test_only_owner_can_delete_project(self, client):
        """Editor cannot delete project."""
        owner_token = await register_user(client, "own7@test.com")
        editor_token = await register_user(client, "edit7@test.com")
        oh = auth_header(owner_token)
        eh = auth_header(editor_token)

        resp = await client.post("/api/projects", json={"name": "OnlyOwnerDeletes"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "edit7@test.com", "role": "editor"},
            headers=oh,
        )

        delete = await client.delete(f"/api/projects/{pid}", headers=eh)
        assert delete.status_code == 403

    @pytest.mark.asyncio
    async def test_only_owner_can_manage_members(self, client):
        """Editor cannot add members."""
        owner_token = await register_user(client, "own8@test.com")
        editor_token = await register_user(client, "edit8@test.com")
        await register_user(client, "extra8@test.com")
        oh = auth_header(owner_token)
        eh = auth_header(editor_token)

        resp = await client.post("/api/projects", json={"name": "MembMgmt"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "edit8@test.com", "role": "editor"},
            headers=oh,
        )

        # Editor tries to add a member
        add = await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "extra8@test.com", "role": "viewer"},
            headers=eh,
        )
        assert add.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_remove_owner(self, client):
        """Cannot remove the owner membership."""
        token = await register_user(client, "own9@test.com")
        h = auth_header(token)

        resp = await client.post("/api/projects", json={"name": "NoRemoveOwner"}, headers=h)
        pid = resp.json()["id"]

        members = await client.get(f"/api/projects/{pid}/members", headers=h)
        owner_member_id = members.json()[0]["id"]

        delete = await client.delete(f"/api/projects/{pid}/members/{owner_member_id}", headers=h)
        assert delete.status_code == 400

    @pytest.mark.asyncio
    async def test_update_member_role(self, client):
        """Owner can change viewer to editor."""
        owner_token = await register_user(client, "own10@test.com")
        viewer_token = await register_user(client, "view10@test.com")
        oh = auth_header(owner_token)

        resp = await client.post("/api/projects", json={"name": "RoleChange"}, headers=oh)
        pid = resp.json()["id"]

        add = await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "view10@test.com", "role": "viewer"},
            headers=oh,
        )
        mid = add.json()["id"]

        update = await client.put(
            f"/api/projects/{pid}/members/{mid}",
            json={"role": "editor"},
            headers=oh,
        )
        assert update.status_code == 200
        assert update.json()["role"] == "editor"

    @pytest.mark.asyncio
    async def test_remove_member(self, client):
        """Owner can remove a member."""
        owner_token = await register_user(client, "own11@test.com")
        viewer_token = await register_user(client, "view11@test.com")
        oh = auth_header(owner_token)

        resp = await client.post("/api/projects", json={"name": "RemoveMem"}, headers=oh)
        pid = resp.json()["id"]

        add = await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "view11@test.com", "role": "viewer"},
            headers=oh,
        )
        mid = add.json()["id"]

        delete = await client.delete(f"/api/projects/{pid}/members/{mid}", headers=oh)
        assert delete.status_code == 204

        # Verify removed
        members = await client.get(f"/api/projects/{pid}/members", headers=oh)
        emails = [m["email"] for m in members.json()]
        assert "view11@test.com" not in emails

    @pytest.mark.asyncio
    async def test_shared_project_visible_in_list(self, client):
        """Shared projects appear in viewer's project list."""
        owner_token = await register_user(client, "own12@test.com")
        viewer_token = await register_user(client, "view12@test.com")
        oh = auth_header(owner_token)
        vh = auth_header(viewer_token)

        resp = await client.post("/api/projects", json={"name": "SharedVis"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "view12@test.com", "role": "viewer"},
            headers=oh,
        )

        projects = await client.get("/api/projects", headers=vh)
        assert projects.status_code == 200
        names = [p["name"] for p in projects.json()]
        assert "SharedVis" in names

    @pytest.mark.asyncio
    async def test_duplicate_member_rejected(self, client):
        """Adding same user twice is rejected."""
        owner_token = await register_user(client, "own13@test.com")
        await register_user(client, "dup13@test.com")
        oh = auth_header(owner_token)

        resp = await client.post("/api/projects", json={"name": "NoDups"}, headers=oh)
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "dup13@test.com", "role": "viewer"},
            headers=oh,
        )

        dup = await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "dup13@test.com", "role": "editor"},
            headers=oh,
        )
        assert dup.status_code == 400
