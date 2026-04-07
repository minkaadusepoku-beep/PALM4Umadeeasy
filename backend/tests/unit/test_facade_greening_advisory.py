"""Tests for facade greening advisory module.

CRITICAL CONTRACT under test: every response must be flagged as
advisory_non_palm and coupled_with_palm=False. Tests assert this on
every public function and API endpoint to prevent accidental mixing
with PALM-coupled outputs.
"""
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
from src.science.facade_greening_advisory import (
    FacadeGreeningInput,
    estimate_pollutant_uptake,
    estimate_cooling_effect,
    estimate_energy_savings,
    full_advisory,
    list_supported_species,
)


def _assert_advisory_provenance(d: dict) -> None:
    assert d["result_kind"] == "advisory_non_palm"
    assert d["coupled_with_palm"] is False
    assert "warning" in d
    assert d["uncertainty"] == "high"


class TestFacadeGreeningCore:
    def test_pollutant_uptake_basic(self):
        inp = FacadeGreeningInput(facade_area_m2=100.0, species="hedera_helix")
        out = estimate_pollutant_uptake(inp)
        _assert_advisory_provenance(out)
        assert "PM10" in out["pollutants"]
        assert out["pollutants"]["PM10"]["central_kg_per_year"] > 0
        assert (
            out["pollutants"]["PM10"]["low_kg_per_year"]
            <= out["pollutants"]["PM10"]["central_kg_per_year"]
            <= out["pollutants"]["PM10"]["high_kg_per_year"]
        )

    def test_pollutant_uptake_scales_linearly_with_area(self):
        a = estimate_pollutant_uptake(
            FacadeGreeningInput(facade_area_m2=50.0, species="hedera_helix")
        )
        b = estimate_pollutant_uptake(
            FacadeGreeningInput(facade_area_m2=100.0, species="hedera_helix")
        )
        ratio = (
            b["pollutants"]["PM10"]["central_kg_per_year"]
            / a["pollutants"]["PM10"]["central_kg_per_year"]
        )
        assert abs(ratio - 2.0) < 0.01

    def test_coverage_fraction_zero(self):
        inp = FacadeGreeningInput(
            facade_area_m2=100.0, species="hedera_helix", coverage_fraction=0.0
        )
        out = estimate_pollutant_uptake(inp)
        assert out["pollutants"]["PM10"]["central_kg_per_year"] == 0.0

    def test_invalid_species_raises(self):
        with pytest.raises(ValueError, match="unknown species"):
            estimate_pollutant_uptake(
                FacadeGreeningInput(facade_area_m2=10.0, species="banana")  # type: ignore[arg-type]
            )

    def test_invalid_area_raises(self):
        with pytest.raises(ValueError):
            estimate_pollutant_uptake(
                FacadeGreeningInput(facade_area_m2=0.0, species="hedera_helix")
            )

    def test_invalid_coverage_raises(self):
        with pytest.raises(ValueError):
            estimate_pollutant_uptake(
                FacadeGreeningInput(
                    facade_area_m2=10.0,
                    species="hedera_helix",
                    coverage_fraction=1.5,
                )
            )

    def test_cooling_effect_provenance(self):
        out = estimate_cooling_effect(
            FacadeGreeningInput(facade_area_m2=100.0, species="hedera_helix")
        )
        _assert_advisory_provenance(out)
        assert out["delta_t_celsius"]["low"] < out["delta_t_celsius"]["high"]

    def test_energy_savings_provenance(self):
        out = estimate_energy_savings(
            FacadeGreeningInput(facade_area_m2=100.0, species="parthenocissus")
        )
        _assert_advisory_provenance(out)
        assert (
            0
            <= out["summer_cooling_load_reduction_fraction"]["low"]
            <= out["summer_cooling_load_reduction_fraction"]["high"]
            <= 1
        )

    def test_full_advisory_carries_provenance_at_every_level(self):
        out = full_advisory(
            FacadeGreeningInput(facade_area_m2=120.0, species="generic_climber")
        )
        _assert_advisory_provenance(out)
        _assert_advisory_provenance(out["pollutant_uptake"])
        _assert_advisory_provenance(out["cooling_effect"])
        _assert_advisory_provenance(out["energy_savings"])
        assert "disclaimer" in out
        assert "PALM" in out["disclaimer"]

    def test_list_species(self):
        s = list_supported_species()
        assert any(x["id"] == "hedera_helix" for x in s)
        for entry in s:
            assert entry["lai_low"] < entry["lai_central"] < entry["lai_high"]


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


async def _auth(client: AsyncClient) -> str:
    r = await client.post(
        "/api/auth/register",
        json={"email": "facade@test.com", "password": "Test1234"},
    )
    return r.json()["access_token"]


@pytest.mark.asyncio
class TestFacadeGreeningAPI:
    async def test_advisory_endpoint_returns_provenance(self, client):
        token = await _auth(client)
        r = await client.post(
            "/api/advisory/facade-greening",
            json={
                "facade_area_m2": 80.0,
                "species": "hedera_helix",
                "coverage_fraction": 0.9,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        _assert_advisory_provenance(data)
        assert data["pollutant_uptake"]["coupled_with_palm"] is False

    async def test_species_endpoint_flagged(self, client):
        token = await _auth(client)
        r = await client.get(
            "/api/advisory/facade-greening/species",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["result_kind"] == "advisory_non_palm"
        assert data["coupled_with_palm"] is False
        assert len(data["species"]) >= 1

    async def test_advisory_rejects_bad_input(self, client):
        token = await _auth(client)
        r = await client.post(
            "/api/advisory/facade-greening",
            json={
                "facade_area_m2": -1.0,
                "species": "hedera_helix",
                "coverage_fraction": 0.5,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400

    async def test_advisory_requires_auth(self, client):
        r = await client.post(
            "/api/advisory/facade-greening",
            json={"facade_area_m2": 80.0, "species": "hedera_helix"},
        )
        assert r.status_code in (401, 403)
