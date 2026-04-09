"""Regression test for building rasterisation (ADR-004 §5, §9).

A fixed input snapshot + edit list must produce the exact same
building_height_2d array. This is the test that protects scientific
reproducibility.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.models.scenario import (
    BuildingEditAdd,
    BuildingEditRemove,
    BuildingsEdits,
    BoundingBox,
    DomainConfig,
    Scenario,
    ScenarioType,
)
from src.snapshots.buildings import register_snapshot, clear_in_memory_snapshots

# We need netCDF4 for reading the output
netCDF4 = pytest.importorskip("netCDF4")

LON0, LAT0 = 6.9603, 50.9375
DEG_PER_M_LAT = 1.0 / 111_320.0


def _deg_per_m_lon(lat: float) -> float:
    return 1.0 / (111_320.0 * math.cos(math.radians(lat)))


def _square_polygon(cx: float, cy: float, side_m: float) -> dict:
    half = side_m / 2.0
    dlat = half * DEG_PER_M_LAT
    dlon = half * _deg_per_m_lon(cy)
    coords = [
        [cx - dlon, cy - dlat],
        [cx + dlon, cy - dlat],
        [cx + dlon, cy + dlat],
        [cx - dlon, cy + dlat],
        [cx - dlon, cy - dlat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def _make_scenario(resolution_m: float = 10.0) -> Scenario:
    half_lat = 100 * DEG_PER_M_LAT
    half_lon = 100 * _deg_per_m_lon(LAT0)
    bbox = BoundingBox(
        west=LON0 - half_lon,
        east=LON0 + half_lon,
        south=LAT0 - half_lat,
        north=LAT0 + half_lat,
    )
    return Scenario(
        name="raster-test",
        scenario_type=ScenarioType.BASELINE,
        domain=DomainConfig(bbox=bbox, resolution_m=resolution_m, epsg=4326, nz=20, dz=2.0),
    )


@pytest.fixture(autouse=True)
def _clean_snapshots():
    yield
    clear_in_memory_snapshots()


def test_rasterise_single_building():
    """A single 40x40 m building at the domain centre should fill ~16 cells at 10 m resolution."""
    from src.translation.static_driver import generate_static_driver

    base_buildings = [{
        "id": "b1",
        "geometry": _square_polygon(LON0, LAT0, 40.0),
        "height_m": 15.0,
        "roof_type": "flat",
        "wall_material_id": "concrete",
    }]
    register_snapshot("test-snap", base_buildings)

    s = _make_scenario(resolution_m=10.0)
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="test-snap",
        edits=[],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = generate_static_driver(s, Path(tmp) / "static.nc")
        ds = netCDF4.Dataset(str(out), "r")
        try:
            h = ds.variables["buildings_2d"][:, :]
            bid = ds.variables["building_id"][:, :]
            btype = ds.variables["building_type"][:, :]

            # Some cells should have height = 15.0
            building_cells = h[h > 0]
            assert len(building_cells) > 0, "No building cells rasterised"
            assert np.allclose(building_cells, 15.0), f"Expected 15.0, got {np.unique(building_cells)}"

            # Building ID should be 1 for all building cells
            id_cells = bid[h > 0]
            assert np.all(id_cells == 1)

            # Building type for concrete/flat = 3
            type_cells = btype[h > 0]
            assert np.all(type_cells == 3)
        finally:
            ds.close()


def test_add_edit_appears_in_raster():
    """An 'add' edit should create a new building in the rasterised output."""
    from src.translation.static_driver import generate_static_driver

    register_snapshot("empty-snap", [])

    offset_lon = LON0 + 30 * _deg_per_m_lon(LAT0)
    s = _make_scenario(resolution_m=10.0)
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="empty-snap",
        edits=[
            BuildingEditAdd(
                id="e1",
                op="add",
                geometry=_square_polygon(LON0, LAT0, 30.0),
                height_m=20.0,
                wall_material_id="brick",
                roof_type="pitched",
            ),
        ],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = generate_static_driver(s, Path(tmp) / "static.nc")
        ds = netCDF4.Dataset(str(out), "r")
        try:
            h = ds.variables["buildings_2d"][:, :]
            building_cells = h[h > 0]
            assert len(building_cells) > 0
            assert np.allclose(building_cells, 20.0)
        finally:
            ds.close()


def test_remove_edit_removes_from_raster():
    """A 'remove' edit should eliminate a base building from the output."""
    from src.translation.static_driver import generate_static_driver

    base = [{
        "id": "b1",
        "geometry": _square_polygon(LON0, LAT0, 40.0),
        "height_m": 10.0,
    }]
    register_snapshot("rm-snap", base)

    s = _make_scenario(resolution_m=10.0)
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="rm-snap",
        edits=[
            BuildingEditRemove(id="e1", op="remove", target_building_id="b1"),
        ],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = generate_static_driver(s, Path(tmp) / "static.nc")
        ds = netCDF4.Dataset(str(out), "r")
        try:
            h = ds.variables["buildings_2d"][:, :]
            building_cells = h[h > 0]
            assert len(building_cells) == 0, "Removed building still appears in raster"
        finally:
            ds.close()


def test_deterministic_output():
    """Running the same scenario twice must produce byte-identical building arrays."""
    from src.translation.static_driver import generate_static_driver

    base = [{
        "id": "b1",
        "geometry": _square_polygon(LON0, LAT0, 30.0),
        "height_m": 12.0,
        "roof_type": "flat",
        "wall_material_id": "concrete",
    }]
    register_snapshot("det-snap", base)

    s = _make_scenario(resolution_m=10.0)
    s.buildings_edits = BuildingsEdits(
        base_snapshot_id="det-snap",
        edits=[
            BuildingEditAdd(
                id="e1", op="add",
                geometry=_square_polygon(LON0 + 60 * _deg_per_m_lon(LAT0), LAT0, 20.0),
                height_m=25.0, wall_material_id="glass", roof_type="flat",
            ),
        ],
    )

    with tempfile.TemporaryDirectory() as tmp:
        out1 = generate_static_driver(s, Path(tmp) / "run1.nc")
        out2 = generate_static_driver(s, Path(tmp) / "run2.nc")

        ds1 = netCDF4.Dataset(str(out1), "r")
        ds2 = netCDF4.Dataset(str(out2), "r")
        try:
            h1 = ds1.variables["buildings_2d"][:, :]
            h2 = ds2.variables["buildings_2d"][:, :]
            np.testing.assert_array_equal(h1, h2, "Rasterisation is not deterministic")

            id1 = ds1.variables["building_id"][:, :]
            id2 = ds2.variables["building_id"][:, :]
            np.testing.assert_array_equal(id1, id2)
        finally:
            ds1.close()
            ds2.close()
