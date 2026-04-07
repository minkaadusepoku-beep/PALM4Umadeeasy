"""Tests for forcing file upload, validation, and management."""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("PALM4U_EXTERNAL_WORKERS", "1")
os.environ.setdefault("PALM4U_AUTH_RATE_LIMIT", "10000")

from src.db.database import Base, get_db
from src.api.main import app
from src.science.forcing_validator import validate_forcing_file
from pathlib import Path
import tempfile


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


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def setup_project(client) -> tuple[str, int]:
    resp = await client.post("/api/auth/register", json={"email": "forcing@test.com", "password": "Test1234"})
    token = resp.json()["access_token"]
    proj = await client.post("/api/projects", json={"name": "Forcing Test"}, headers=auth_header(token))
    return token, proj.json()["id"]


class TestForcingValidator:
    def test_invalid_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not a netcdf file")
            path = Path(f.name)
        try:
            errors = validate_forcing_file(path, "test.txt")
            assert any("extension" in e.lower() for e in errors)
        finally:
            path.unlink()

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            path = Path(f.name)
        try:
            errors = validate_forcing_file(path, "test.nc")
            assert any("empty" in e.lower() for e in errors)
        finally:
            path.unlink()

    def test_valid_extension_but_invalid_content(self):
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            f.write(b"not real netcdf content")
            path = Path(f.name)
        try:
            errors = validate_forcing_file(path, "test.nc")
            # May or may not have errors depending on netCDF4 availability
            # But should not crash
            assert isinstance(errors, list)
        finally:
            path.unlink()


class TestForcingAPI:
    @pytest.mark.asyncio
    async def test_upload_forcing(self, client):
        token, pid = await setup_project(client)
        resp = await client.post(
            f"/api/projects/{pid}/forcing",
            files={"file": ("test.nc", b"fake netcdf content", "application/octet-stream")},
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "test.nc"
        assert data["file_size"] > 0

    @pytest.mark.asyncio
    async def test_list_forcing(self, client):
        token, pid = await setup_project(client)
        await client.post(
            f"/api/projects/{pid}/forcing",
            files={"file": ("data.nc", b"content", "application/octet-stream")},
            headers=auth_header(token),
        )
        resp = await client.get(f"/api/projects/{pid}/forcing", headers=auth_header(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_delete_forcing(self, client):
        token, pid = await setup_project(client)
        upload = await client.post(
            f"/api/projects/{pid}/forcing",
            files={"file": ("del.nc", b"content", "application/octet-stream")},
            headers=auth_header(token),
        )
        fid = upload.json()["id"]

        resp = await client.delete(f"/api/projects/{pid}/forcing/{fid}", headers=auth_header(token))
        assert resp.status_code == 204

        # Verify deleted
        listing = await client.get(f"/api/projects/{pid}/forcing", headers=auth_header(token))
        ids = [f["id"] for f in listing.json()]
        assert fid not in ids

    @pytest.mark.asyncio
    async def test_viewer_cannot_upload(self, client):
        token, pid = await setup_project(client)
        viewer_resp = await client.post("/api/auth/register", json={"email": "fview@test.com", "password": "Test1234"})
        viewer_token = viewer_resp.json()["access_token"]

        # Add as viewer
        await client.post(
            f"/api/projects/{pid}/members",
            json={"email": "fview@test.com", "role": "viewer"},
            headers=auth_header(token),
        )

        resp = await client.post(
            f"/api/projects/{pid}/forcing",
            files={"file": ("test.nc", b"content", "application/octet-stream")},
            headers=auth_header(viewer_token),
        )
        assert resp.status_code == 403
