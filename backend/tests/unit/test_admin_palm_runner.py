"""
Tests for the runtime-editable PALM runner config (ADR-005 §Runtime config).

Covers:
- GET /api/admin/palm-runner
- PUT /api/admin/palm-runner (save, clear, field-level merge with env)
- POST /api/admin/palm-runner/test (with and without ad-hoc overrides)
- GET /api/runner-info (read-only hint for non-admin editors)

The "Test connection" endpoint is exercised against a stand-in ASGI app that
impersonates the Linux worker's /health endpoint, so we can assert both
success and failure paths without needing a real worker running.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("PALM4U_EXTERNAL_WORKERS", "1")
os.environ.setdefault("PALM4U_AUTH_RATE_LIMIT", "10000")

from src.db.database import Base, get_db  # noqa: E402
from src.db.models import User  # noqa: E402
from src.api.main import app  # noqa: E402


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
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(db_engine, session_factory):
    async def override_get_db():
        async with session_factory() as session:
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


async def _make_admin(session_factory, email: str) -> None:
    async with session_factory() as s:
        await s.execute(update(User).where(User.email == email).values(is_admin=True))
        await s.commit()


async def _admin_token(client: AsyncClient, session_factory, email: str = "admin@test.com") -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "Test1234"})
    await _make_admin(session_factory, email)
    login = await client.post(
        "/api/auth/login", data={"username": email, "password": "Test1234"}
    )
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# GET /api/admin/palm-runner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetPalmRunner:
    async def test_non_admin_blocked(self, client):
        r = await client.post("/api/auth/register", json={"email": "u@test.com", "password": "Test1234"})
        token = r.json()["access_token"]
        resp = await client.get("/api/admin/palm-runner", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_defaults_to_stub_with_env_source(self, client, session_factory, monkeypatch):
        monkeypatch.delenv("PALM_RUNNER_MODE", raising=False)
        monkeypatch.delenv("PALM_REMOTE_URL", raising=False)
        monkeypatch.delenv("PALM_REMOTE_TOKEN", raising=False)
        token = await _admin_token(client, session_factory)
        resp = await client.get("/api/admin/palm-runner", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "stub"
        assert body["mode_source"] == "default"
        assert body["token_configured"] is False
        # GET must never leak the raw token.
        assert "remote_token" not in body

    async def test_reflects_env_mode(self, client, session_factory, monkeypatch):
        monkeypatch.setenv("PALM_RUNNER_MODE", "remote")
        monkeypatch.setenv("PALM_REMOTE_URL", "http://env-worker:8765")
        monkeypatch.setenv("PALM_REMOTE_TOKEN", "env-tok")
        token = await _admin_token(client, session_factory)
        resp = await client.get("/api/admin/palm-runner", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        assert body["mode"] == "remote"
        assert body["mode_source"] == "env"
        assert body["remote_url"] == "http://env-worker:8765"
        assert body["remote_url_source"] == "env"
        assert body["token_configured"] is True
        assert body["remote_token_source"] == "env"


# ---------------------------------------------------------------------------
# PUT /api/admin/palm-runner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPutPalmRunner:
    async def test_save_full_config(self, client, session_factory):
        token = await _admin_token(client, session_factory)
        resp = await client.put(
            "/api/admin/palm-runner",
            json={
                "mode": "remote",
                "remote_url": "http://saved:8765",
                "remote_token": "secret",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "remote"
        assert body["mode_source"] == "db"
        assert body["remote_url"] == "http://saved:8765"
        assert body["remote_url_source"] == "db"
        assert body["token_configured"] is True
        assert body["remote_token_source"] == "db"
        # Never return the raw token.
        assert "remote_token" not in body

    async def test_clear_url_falls_back_to_env(self, client, session_factory, monkeypatch):
        monkeypatch.setenv("PALM_REMOTE_URL", "http://fallback:8765")
        token = await _admin_token(client, session_factory)
        # First save both.
        await client.put(
            "/api/admin/palm-runner",
            json={"mode": "remote", "remote_url": "http://db:8765", "remote_token": "t"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Now clear URL only.
        resp = await client.put(
            "/api/admin/palm-runner",
            json={"mode": "remote", "remote_url": None, "remote_token": "t"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert body["remote_url"] == "http://fallback:8765"
        assert body["remote_url_source"] == "env"

    async def test_invalid_mode_rejected(self, client, session_factory):
        token = await _admin_token(client, session_factory)
        resp = await client.put(
            "/api/admin/palm-runner",
            json={"mode": "quantum"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_audit_log_records_save(self, client, session_factory):
        token = await _admin_token(client, session_factory)
        await client.put(
            "/api/admin/palm-runner",
            json={"mode": "remote", "remote_url": "http://w:8765", "remote_token": "supersecret"},
            headers={"Authorization": f"Bearer {token}"},
        )
        log_resp = await client.get(
            "/api/admin/audit-log?action=palm_runner_config_update",
            headers={"Authorization": f"Bearer {token}"},
        )
        entries = log_resp.json()
        assert len(entries) >= 1
        detail = entries[0]["detail"]
        # The token itself must not appear in the audit log.
        assert "supersecret" not in detail
        assert "mode=remote" in detail
        assert "http://w:8765" in detail

    async def test_db_config_wins_over_env(self, client, session_factory, monkeypatch):
        monkeypatch.setenv("PALM_RUNNER_MODE", "stub")
        monkeypatch.setenv("PALM_REMOTE_URL", "http://env:8765")
        token = await _admin_token(client, session_factory)
        await client.put(
            "/api/admin/palm-runner",
            json={"mode": "remote", "remote_url": "http://db:8765", "remote_token": "t"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.get("/api/admin/palm-runner", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        assert body["mode"] == "remote"
        assert body["mode_source"] == "db"
        assert body["remote_url"] == "http://db:8765"
        assert body["remote_url_source"] == "db"


# ---------------------------------------------------------------------------
# POST /api/admin/palm-runner/test — ad-hoc probe
# ---------------------------------------------------------------------------

class _FakeAsyncResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
class TestTestConnection:
    async def test_success_reports_worker_version(self, client, session_factory, monkeypatch):
        token = await _admin_token(client, session_factory)

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                assert "Bearer" in headers["Authorization"]
                return _FakeAsyncResponse(200, {"status": "ok", "palm_version": "23.10"})

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

        resp = await client.post(
            "/api/admin/palm-runner/test",
            json={"remote_url": "http://probe:8765", "remote_token": "abc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["http_status"] == 200
        assert body["url"].endswith("/health")
        assert body["worker"]["palm_version"] == "23.10"

    async def test_bad_status_reports_error(self, client, session_factory, monkeypatch):
        token = await _admin_token(client, session_factory)

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                return _FakeAsyncResponse(401)

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

        resp = await client.post(
            "/api/admin/palm-runner/test",
            json={"remote_url": "http://probe:8765", "remote_token": "bad"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert body["ok"] is False
        assert body["http_status"] == 401
        assert "401" in body["error"]

    async def test_connection_refused_reports_ok_false(self, client, session_factory, monkeypatch):
        token = await _admin_token(client, session_factory)

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                import httpx
                raise httpx.ConnectError("nope")

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

        resp = await client.post(
            "/api/admin/palm-runner/test",
            json={"remote_url": "http://nobody:1", "remote_token": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert body["ok"] is False
        assert body["http_status"] is None
        assert "connection failed" in body["error"]

    async def test_uses_saved_config_when_no_override(self, client, session_factory, monkeypatch):
        token = await _admin_token(client, session_factory)
        # Save a config that the probe should pick up.
        await client.put(
            "/api/admin/palm-runner",
            json={"mode": "remote", "remote_url": "http://saved:8765", "remote_token": "t"},
            headers={"Authorization": f"Bearer {token}"},
        )

        captured = {}

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, headers=None):
                captured["url"] = url
                captured["auth"] = headers["Authorization"]
                return _FakeAsyncResponse(200, {"status": "ok"})

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

        resp = await client.post(
            "/api/admin/palm-runner/test",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert captured["url"] == "http://saved:8765/health"
        assert captured["auth"] == "Bearer t"

    async def test_missing_url_reports_not_ok(self, client, session_factory, monkeypatch):
        monkeypatch.delenv("PALM_REMOTE_URL", raising=False)
        monkeypatch.delenv("PALM_REMOTE_TOKEN", raising=False)
        token = await _admin_token(client, session_factory)
        resp = await client.post(
            "/api/admin/palm-runner/test",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert body["ok"] is False
        assert "No worker URL" in body["error"]


# ---------------------------------------------------------------------------
# GET /api/runner-info — public routing hint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunnerInfo:
    async def test_available_to_non_admin(self, client, monkeypatch):
        monkeypatch.delenv("PALM_RUNNER_MODE", raising=False)
        r = await client.post("/api/auth/register", json={"email": "e@test.com", "password": "Test1234"})
        token = r.json()["access_token"]
        resp = await client.get("/api/runner-info", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "stub"
        assert body["ready"] is True
        assert "Stub" in body["label"]
        # Token must never be exposed here.
        assert "token" not in body or "remote_token" not in body

    async def test_reports_remote_not_ready_when_unconfigured(self, client, monkeypatch):
        monkeypatch.setenv("PALM_RUNNER_MODE", "remote")
        monkeypatch.delenv("PALM_REMOTE_URL", raising=False)
        monkeypatch.delenv("PALM_REMOTE_TOKEN", raising=False)
        r = await client.post("/api/auth/register", json={"email": "x@test.com", "password": "Test1234"})
        token = r.json()["access_token"]
        resp = await client.get("/api/runner-info", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        assert body["mode"] == "remote"
        assert body["ready"] is False
        assert "NOT CONFIGURED" in body["label"]

    async def test_requires_auth(self, client):
        resp = await client.get("/api/runner-info")
        assert resp.status_code in (401, 403)
