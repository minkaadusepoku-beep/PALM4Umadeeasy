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

async def register_and_get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123"},
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
            json={"email": "new@example.com", "password": "pass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "pass123"},
        )
        resp = await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "pass123"},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "login@example.com", "password": "pass123"},
        )
        resp = await client.post(
            "/api/auth/login",
            data={"username": "login@example.com", "password": "pass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "wrong@example.com", "password": "pass123"},
        )
        resp = await client.post(
            "/api/auth/login",
            data={"username": "wrong@example.com", "password": "badpassword"},
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
            json={"email": "a@test.com", "password": "pass123"},
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
            json={"email": "b@test.com", "password": "pass123"},
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
        assert data["status"] == "pending"
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
        assert data["status"] == "pending"

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
