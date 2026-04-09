"""Unit tests for ADR-004 building geometry edit validation."""

from __future__ import annotations

import math

import pytest

from src.models.scenario import (
    BuildingEditAdd,
    BuildingEditModify,
    BuildingEditRemove,
    BuildingsEdits,
    DataQualityTier,
    DomainConfig,
    BoundingBox,
    Scenario,
    ScenarioType,
)
from src.validation.buildings import (
    validate_buildings_edits,
    resolve_buildings,
    downgraded_buildings_tier,
    MIN_BUILDING_AREA_M2,
)


# ---------------------------------------------------------------------------
# Helpers — build a deterministic small WGS84 domain over central Cologne.
# ---------------------------------------------------------------------------

LON0, LAT0 = 6.9603, 50.9375  # near Cologne cathedral
DEG_PER_M_LAT = 1.0 / 111_320.0


def _deg_per_m_lon(lat: float) -> float:
    return 1.0 / (111_320.0 * math.cos(math.radians(lat)))


def _square_polygon(center_lon: float, center_lat: float, side_m: float) -> dict:
    half = side_m / 2.0
    dlat = half * DEG_PER_M_LAT
    dlon = half * _deg_per_m_lon(center_lat)
    coords = [
        [center_lon - dlon, center_lat - dlat],
        [center_lon + dlon, center_lat - dlat],
        [center_lon + dlon, center_lat + dlat],
        [center_lon - dlon, center_lat + dlat],
        [center_lon - dlon, center_lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def _make_scenario(resolution_m: float = 2.0) -> Scenario:
    half_lat = 200 * DEG_PER_M_LAT  # ~400 m N-S
    half_lon = 200 * _deg_per_m_lon(LAT0)
    bbox = BoundingBox(
        west=LON0 - half_lon,
        east=LON0 + half_lon,
        south=LAT0 - half_lat,
        north=LAT0 + half_lat,
    )
    return Scenario(
        name="test",
        scenario_type=ScenarioType.BASELINE,
        domain=DomainConfig(bbox=bbox, resolution_m=resolution_m, epsg=4326, nz=20, dz=2.0),
    )


def _add(eid: str, lon: float, lat: float, side_m: float, height_m: float = 12.0) -> BuildingEditAdd:
    return BuildingEditAdd(
        id=eid,
        op="add",
        geometry=_square_polygon(lon, lat, side_m),
        height_m=height_m,
        wall_material_id="concrete",
    )


# ---------------------------------------------------------------------------
# Rule 1: well-formed geometry
# ---------------------------------------------------------------------------

def test_add_with_valid_polygon_passes():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 10.0)],
    )
    result = validate_buildings_edits(s, base_buildings=[])
    assert result.valid, result.errors


def test_unclosed_polygon_rejected():
    s = _make_scenario()
    bad_geom = _square_polygon(LON0, LAT0, 10.0)
    bad_geom["coordinates"][0] = bad_geom["coordinates"][0][:-1]  # drop closing point
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[BuildingEditAdd(id="e1", op="add", geometry=bad_geom, height_m=10.0, wall_material_id="x")],
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "add.invalid_geometry" for e in result.errors)


# ---------------------------------------------------------------------------
# Rule 2: minimum footprint area
# ---------------------------------------------------------------------------

def test_too_small_footprint_rejected():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 2.5)],  # 6.25 m^2 < 9 m^2
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "add.area_too_small" for e in result.errors)


# ---------------------------------------------------------------------------
# Rule 3: minimum edge length
# ---------------------------------------------------------------------------

def test_edge_below_two_dx_rejected():
    s = _make_scenario(resolution_m=10.0)  # 2*dx = 20 m
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 15.0)],  # area ok (225 m²) but edge=15 m < 20 m
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "add.edge_too_short" for e in result.errors)


# ---------------------------------------------------------------------------
# Rule 4: height bounds + soft warning
# ---------------------------------------------------------------------------

def test_height_above_soft_warn_warns_but_passes():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 10.0, height_m=120.0)],
    )
    result = validate_buildings_edits(s, [])
    assert result.valid
    assert any(w.code == "add.height_above_soft_warn" for w in result.warnings)


def test_height_above_max_rejected_at_pydantic_layer():
    with pytest.raises(Exception):
        BuildingEditAdd(
            id="e1", op="add", geometry=_square_polygon(LON0, LAT0, 10.0),
            height_m=400.0, wall_material_id="x",
        )


# ---------------------------------------------------------------------------
# Rule 5: inside the project domain
# ---------------------------------------------------------------------------

def test_outside_domain_rejected():
    s = _make_scenario()
    far_lon = LON0 + 0.05  # ~3.5 km east, well outside the ~200 m domain
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", far_lon, LAT0, 10.0)],
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "add.outside_domain" for e in result.errors)


# ---------------------------------------------------------------------------
# Rule 6: no overlap
# ---------------------------------------------------------------------------

def test_overlap_with_base_building_rejected():
    s = _make_scenario()
    base = [{
        "id": "osm:way/1",
        "geometry": _square_polygon(LON0, LAT0, 20.0),
        "height_m": 10.0,
    }]
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="snap",
        edits=[_add("e1", LON0, LAT0, 10.0)],  # nested inside base
    )
    result = validate_buildings_edits(s, base)
    assert not result.valid
    assert any(e.code == "add.overlap" for e in result.errors)


def test_non_overlapping_passes():
    s = _make_scenario()
    base = [{
        "id": "osm:way/1",
        "geometry": _square_polygon(LON0, LAT0, 10.0),
        "height_m": 10.0,
    }]
    other_lon = LON0 + 50 * _deg_per_m_lon(LAT0)
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="snap",
        edits=[_add("e1", other_lon, LAT0, 10.0)],
    )
    result = validate_buildings_edits(s, base)
    assert result.valid, result.errors


# ---------------------------------------------------------------------------
# Rule 7: reference integrity for modify / remove
# ---------------------------------------------------------------------------

def test_modify_unknown_target_rejected():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[BuildingEditModify(id="e1", op="modify", target_building_id="ghost", set={"height_m": 20.0})],
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "modify.unknown_target" for e in result.errors)


def test_remove_unknown_target_rejected():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[BuildingEditRemove(id="e1", op="remove", target_building_id="ghost")],
    )
    result = validate_buildings_edits(s, [])
    assert not result.valid
    assert any(e.code == "remove.unknown_target" for e in result.errors)


def test_remove_then_modify_chain_fails():
    s = _make_scenario()
    base = [{
        "id": "osm:way/1",
        "geometry": _square_polygon(LON0, LAT0, 10.0),
        "height_m": 10.0,
    }]
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="snap",
        edits=[
            BuildingEditRemove(id="e1", op="remove", target_building_id="osm:way/1"),
            BuildingEditModify(id="e2", op="modify", target_building_id="osm:way/1", set={"height_m": 20.0}),
        ],
    )
    result = validate_buildings_edits(s, base)
    assert not result.valid


# ---------------------------------------------------------------------------
# Rule 8: ordered, deterministic application
# ---------------------------------------------------------------------------

def test_resolve_applies_edits_in_order():
    base = [
        {"id": "b1", "geometry": _square_polygon(LON0, LAT0, 10.0), "height_m": 10.0},
    ]
    edits = BuildingsEdits(
        base_snapshot_id="snap",
        edits=[
            BuildingEditModify(id="e1", op="modify", target_building_id="b1", set={"height_m": 20.0}),
            BuildingEditRemove(id="e2", op="remove", target_building_id="b1"),
        ],
    )
    resolved = resolve_buildings(base, edits)
    assert resolved == []


def test_resolve_add_then_remove_yields_empty():
    base: list[dict] = []
    add = _add("e1", LON0, LAT0, 10.0)
    edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[add, BuildingEditRemove(id="e2", op="remove", target_building_id="edit:e1")],
    )
    resolved = resolve_buildings(base, edits)
    assert len(resolved) == 0


# ---------------------------------------------------------------------------
# Provenance downgrade (ADR-004 §6, §11.4)
# ---------------------------------------------------------------------------

def test_no_edits_preserves_tier():
    s = _make_scenario()
    assert downgraded_buildings_tier(DataQualityTier.RESEARCH, s, []) == DataQualityTier.RESEARCH


def test_small_edit_caps_tier_at_project():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 10.0, height_m=10.0)],
    )
    assert downgraded_buildings_tier(DataQualityTier.RESEARCH, s, []) == DataQualityTier.PROJECT


def test_tall_added_building_drops_to_screening():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 10.0, height_m=50.0)],  # > 30 m
    )
    assert downgraded_buildings_tier(DataQualityTier.RESEARCH, s, []) == DataQualityTier.SCREENING


def test_large_footprint_added_building_drops_to_screening():
    s = _make_scenario()
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty",
        edits=[_add("e1", LON0, LAT0, 40.0, height_m=10.0)],  # 1600 m² > 1000 m²
    )
    assert downgraded_buildings_tier(DataQualityTier.RESEARCH, s, []) == DataQualityTier.SCREENING
