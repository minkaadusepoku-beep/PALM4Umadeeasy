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

    @pytest.mark.asyncio
    async def test_health_reports_palm_runner_mode(self, client):
        """
        ADR-005: operators must be able to see which PALM backend is active
        from /health alone. Default env in tests is stub mode — assert that
        the component renders cleanly and exposes the mode label.
        """
        resp = await client.get("/api/health")
        runner = resp.json()["components"]["palm_runner"]
        assert runner["status"] == "healthy"
        assert runner["mode"] == "stub"
        assert "palm_version" in runner

    @pytest.mark.asyncio
    async def test_palm_runner_remote_without_config_is_degraded(self, monkeypatch, client):
        """Remote mode from env but no URL/token → degraded, error surfaced."""
        monkeypatch.setenv("PALM_RUNNER_MODE", "remote")
        monkeypatch.setenv("PALM_REMOTE_URL", "")
        monkeypatch.setenv("PALM_REMOTE_TOKEN", "")
        resp = await client.get("/api/health")
        info = resp.json()["components"]["palm_runner"]
        assert info["mode"] == "remote"
        assert info["mode_source"] == "env"
        assert info["token_configured"] is False
        assert info["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_palm_runner_remote_with_config_is_healthy(self, monkeypatch, client):
        """Remote mode with URL + token from env → healthy and sources reported."""
        monkeypatch.setenv("PALM_RUNNER_MODE", "remote")
        monkeypatch.setenv("PALM_REMOTE_URL", "http://worker:8765")
        monkeypatch.setenv("PALM_REMOTE_TOKEN", "tok")
        resp = await client.get("/api/health")
        info = resp.json()["components"]["palm_runner"]
        assert info["status"] == "healthy"
        assert info["mode"] == "remote"
        assert info["remote_url"] == "http://worker:8765"
        assert info["remote_url_source"] == "env"
        assert info["token_configured"] is True
        assert info["remote_token_source"] == "env"

    @pytest.mark.asyncio
    async def test_palm_runner_unknown_mode_falls_back_to_stub(self, monkeypatch, client):
        """Unknown mode value must not crash the app; falls back to stub."""
        monkeypatch.setenv("PALM_RUNNER_MODE", "bogus")
        resp = await client.get("/api/health")
        info = resp.json()["components"]["palm_runner"]
        assert info["mode"] == "stub"
        assert info["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_palm_runner_db_config_overrides_env(self, monkeypatch, client, db_engine):
        """Admin-saved DB row must take precedence over env vars."""
        from src.db.models import PalmRunnerConfig
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        monkeypatch.setenv("PALM_RUNNER_MODE", "stub")
        monkeypatch.setenv("PALM_REMOTE_URL", "")
        monkeypatch.setenv("PALM_REMOTE_TOKEN", "")

        Session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as s:
            s.add(PalmRunnerConfig(
                mode="remote",
                remote_url="http://db-configured:8765",
                remote_token="db-token",
            ))
            await s.commit()

        resp = await client.get("/api/health")
        info = resp.json()["components"]["palm_runner"]
        assert info["mode"] == "remote"
        assert info["mode_source"] == "db"
        assert info["remote_url"] == "http://db-configured:8765"
        assert info["remote_url_source"] == "db"
        assert info["token_configured"] is True
        assert info["remote_token_source"] == "db"


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
