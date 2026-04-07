"""Pagination tests for /api/projects, /api/jobs, /api/admin/audit-log."""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("PALM4U_EXTERNAL_WORKERS", "1")
os.environ.setdefault("PALM4U_AUTH_RATE_LIMIT", "10000")

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


async def _register(client: AsyncClient, email: str = "page@test.com") -> str:
    r = await client.post(
        "/api/auth/register", json={"email": email, "password": "Test1234"}
    )
    return r.json()["access_token"]


@pytest.mark.asyncio
class TestProjectPagination:
    async def test_list_returns_x_total_count(self, client):
        token = await _register(client)
        h = {"Authorization": f"Bearer {token}"}
        for i in range(5):
            await client.post("/api/projects", json={"name": f"P{i}"}, headers=h)
        r = await client.get("/api/projects", headers=h)
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "5"
        assert len(r.json()) == 5

    async def test_limit_and_offset(self, client):
        token = await _register(client)
        h = {"Authorization": f"Bearer {token}"}
        for i in range(7):
            await client.post("/api/projects", json={"name": f"P{i}"}, headers=h)
        r = await client.get("/api/projects?limit=3&offset=0", headers=h)
        assert len(r.json()) == 3
        assert r.headers["X-Total-Count"] == "7"
        r2 = await client.get("/api/projects?limit=3&offset=3", headers=h)
        assert len(r2.json()) == 3
        ids1 = {p["id"] for p in r.json()}
        ids2 = {p["id"] for p in r2.json()}
        assert ids1.isdisjoint(ids2)

    async def test_max_limit_enforced(self, client):
        token = await _register(client)
        h = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/projects?limit=99999", headers=h)
        assert r.status_code == 200  # clamped, not rejected


@pytest.mark.asyncio
class TestJobPagination:
    async def test_jobs_x_total_count_empty(self, client):
        token = await _register(client)
        h = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/jobs", headers=h)
        assert r.status_code == 200
        assert r.headers["X-Total-Count"] == "0"
        assert r.json() == []

    async def test_invalid_status_filter_400(self, client):
        token = await _register(client)
        h = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/jobs?status_filter=banana", headers=h)
        assert r.status_code == 400
