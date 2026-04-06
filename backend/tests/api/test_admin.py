"""Admin API endpoint tests."""

from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("PALM4U_EXTERNAL_WORKERS", "1")
os.environ.setdefault("PALM4U_AUTH_RATE_LIMIT", "10000")

from src.db.database import Base, get_db
from src.db.models import User
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
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


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


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def register(client, email="admin@test.com") -> str:
    resp = await client.post("/api/auth/register", json={"email": email, "password": "Admin1234"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def make_admin(db_session, email="admin@test.com"):
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_admin = True
    await db_session.commit()


class TestAdminEndpoints:

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, client):
        token = await register(client, "nonadmin@test.com")
        resp = await client.get("/api/admin/queue-stats", headers=auth_header(token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_queue_stats(self, client, db_session):
        token = await register(client)
        await make_admin(db_session)
        resp = await client.get("/api/admin/queue-stats", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "stale_workers" in data
        assert "active_workers" in data

    @pytest.mark.asyncio
    async def test_audit_log(self, client, db_session):
        token = await register(client, "auditadmin@test.com")
        await make_admin(db_session, "auditadmin@test.com")
        resp = await client.get("/api/admin/audit-log", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least the register audit entry
        assert len(data) >= 1
        assert data[0]["action"] == "register"

    @pytest.mark.asyncio
    async def test_audit_log_filter(self, client, db_session):
        token = await register(client, "filteradmin@test.com")
        await make_admin(db_session, "filteradmin@test.com")

        # Login to create a login audit entry
        await client.post("/api/auth/login", data={"username": "filteradmin@test.com", "password": "Admin1234"})

        resp = await client.get("/api/admin/audit-log?action=login", headers=auth_header(token))
        data = resp.json()
        for entry in data:
            assert entry["action"] == "login"

    @pytest.mark.asyncio
    async def test_audit_log_pagination(self, client, db_session):
        token = await register(client, "pagadmin@test.com")
        await make_admin(db_session, "pagadmin@test.com")
        resp = await client.get("/api/admin/audit-log?limit=1&offset=0", headers=auth_header(token))
        data = resp.json()
        assert len(data) <= 1
