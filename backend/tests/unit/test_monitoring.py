"""Tests for health, metrics, and request ID middleware."""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["PALM4U_EXTERNAL_WORKERS"] = "1"

from src.db.database import Base, get_db
from src.api.main import app


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
    test_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

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


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in data
        assert "database" in data["components"]
        assert "queue" in data["components"]
        assert "disk" in data["components"]

    @pytest.mark.asyncio
    async def test_health_db_component(self, client):
        resp = await client.get("/api/health")
        db = resp.json()["components"]["database"]
        assert db["status"] == "healthy"
        assert "latency_ms" in db

    @pytest.mark.asyncio
    async def test_health_queue_component(self, client):
        resp = await client.get("/api/health")
        queue = resp.json()["components"]["queue"]
        assert "jobs" in queue
        assert "stale_workers" in queue

    @pytest.mark.asyncio
    async def test_health_disk_component(self, client):
        resp = await client.get("/api/health")
        disk = resp.json()["components"]["disk"]
        assert "free_gb" in disk
        assert "pct_free" in disk


class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_returns_prometheus_format(self, client):
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "palm4u_jobs_total" in body
        assert "palm4u_active_workers" in body
        assert "palm4u_queue_depth" in body
        assert "palm4u_users_total" in body
        assert "palm4u_projects_total" in body

    @pytest.mark.asyncio
    async def test_metrics_no_auth_required(self, client):
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200


class TestRequestID:
    @pytest.mark.asyncio
    async def test_response_has_request_id(self, client):
        resp = await client.get("/api/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_custom_request_id_preserved(self, client):
        resp = await client.get("/api/health", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers["X-Request-ID"] == "my-custom-id"
