"""Tests for expanded admin dashboard: user mgmt + system-wide jobs."""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
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


async def _register(client: AsyncClient, email: str, pw: str = "Test1234") -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": pw})
    return r.json()["access_token"]


@pytest.mark.asyncio
class TestAdminUsers:
    async def test_non_admin_blocked(self, client):
        token = await _register(client, "u1@test.com")
        r = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    async def test_admin_can_list_users(self, client, session_factory):
        token = await _register(client, "admin@test.com")
        await _make_admin(session_factory, "admin@test.com")
        await _register(client, "u2@test.com")
        await _register(client, "u3@test.com")
        r = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "3"
        emails = {u["email"] for u in r.json()}
        assert {"admin@test.com", "u2@test.com", "u3@test.com"} == emails

    async def test_admin_can_deactivate_other_user(self, client, session_factory):
        await _register(client, "admin@test.com")
        await _make_admin(session_factory, "admin@test.com")
        admin_login = await client.post(
            "/api/auth/login", data={"username": "admin@test.com", "password": "Test1234"}
        )
        admin_token = admin_login.json()["access_token"]
        await _register(client, "victim@test.com")

        users = (await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})).json()
        victim_id = next(u["id"] for u in users if u["email"] == "victim@test.com")

        r = await client.patch(
            f"/api/admin/users/{victim_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        # Deactivated user can no longer use their token
        victim_login = await client.post(
            "/api/auth/login", data={"username": "victim@test.com", "password": "Test1234"}
        )
        # Login may succeed but any authenticated request must fail
        victim_token = victim_login.json().get("access_token")
        if victim_token:
            r2 = await client.get(
                "/api/projects", headers={"Authorization": f"Bearer {victim_token}"}
            )
            assert r2.status_code == 403

    async def test_admin_cannot_self_deactivate(self, client, session_factory):
        token = await _register(client, "admin@test.com")
        await _make_admin(session_factory, "admin@test.com")
        # re-login to refresh admin status
        login = await client.post(
            "/api/auth/login", data={"username": "admin@test.com", "password": "Test1234"}
        )
        token = login.json()["access_token"]
        users = (await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})).json()
        admin_id = next(u["id"] for u in users if u["email"] == "admin@test.com")
        r = await client.patch(
            f"/api/admin/users/{admin_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400

    async def test_admin_cannot_self_demote(self, client, session_factory):
        token = await _register(client, "admin@test.com")
        await _make_admin(session_factory, "admin@test.com")
        login = await client.post(
            "/api/auth/login", data={"username": "admin@test.com", "password": "Test1234"}
        )
        token = login.json()["access_token"]
        users = (await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})).json()
        admin_id = next(u["id"] for u in users if u["email"] == "admin@test.com")
        r = await client.patch(
            f"/api/admin/users/{admin_id}",
            json={"is_admin": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
class TestAdminSystemJobs:
    async def test_admin_jobs_endpoint(self, client, session_factory):
        await _register(client, "admin@test.com")
        await _make_admin(session_factory, "admin@test.com")
        login = await client.post(
            "/api/auth/login", data={"username": "admin@test.com", "password": "Test1234"}
        )
        token = login.json()["access_token"]
        r = await client.get("/api/admin/jobs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "0"
        assert r.json() == []

    async def test_non_admin_blocked_from_admin_jobs(self, client):
        token = await _register(client, "u@test.com")
        r = await client.get("/api/admin/jobs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
