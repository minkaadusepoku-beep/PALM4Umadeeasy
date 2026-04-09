"""
Static driver generation: Scenario -> PIDS-compliant NetCDF.

Targets the PALM Input Data Standard (PIDS) directly.
Reference: https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/static
"""

from __future__ import annotations

from pathlib import Path

import netCDF4 as nc
import numpy as np
from shapely.geometry import Polygon, Point

from ..models.scenario import Scenario, TreePlacement, SurfaceChange, GreenRoof
from ..catalogues.loader import get_species, get_surface
from ..validation.buildings import resolve_buildings, _project_factory, _domain_centroid
from ..snapshots.buildings import load_snapshot

FILL_FLOAT = -9999.0
FILL_INT = -9999
FILL_BYTE = np.int8(-127)


def generate_static_driver(scenario: Scenario, output_path: Path) -> Path:
    """Generate a PIDS-compliant static driver NetCDF from a scenario."""
    domain = scenario.domain
    bbox = domain.bbox
    nx, ny = domain.nx, domain.ny
    dx, dy = domain.resolution_m, domain.resolution_m

    # Grid cell center coordinates
    x_coords = np.arange(nx) * dx + dx / 2
    y_coords = np.arange(ny) * dy + dy / 2

    # Maximum tree height determines zlad levels
    max_tree_h = _max_tree_height(scenario.trees) if scenario.trees else 0
    n_zlad = max(1, int(np.ceil(max_tree_h / domain.dz)) + 1) if max_tree_h > 0 else 1
    zlad = np.arange(n_zlad) * domain.dz

    # Resolve buildings from base snapshot + edits (ADR-004 §5)
    edits_obj = scenario.buildings_edits
    if edits_obj:
        base = load_snapshot(edits_obj.base_snapshot_id)
        resolved = resolve_buildings(base, edits_obj)
    else:
        resolved = []

    with nc.Dataset(str(output_path), "w", format="NETCDF4") as ds:
        _write_global_attributes(ds, domain, bbox)
        _write_dimensions(ds, x_coords, y_coords, zlad)
        _write_terrain(ds, nx, ny)
        _write_surface_classification(ds, nx, ny, scenario.surface_changes, bbox, dx, dy)
        if scenario.trees:
            _write_trees(ds, nx, ny, zlad, scenario.trees, bbox, dx, dy, domain.dz)
        _write_buildings(ds, nx, ny, dx, dy, bbox, domain, resolved)

    return output_path


def _max_tree_height(trees: list[TreePlacement]) -> float:
    heights = []
    for t in trees:
        if t.height_m:
            heights.append(t.height_m)
        else:
            sp = get_species(t.species_id)
            heights.append(sp["height_m"]["default"])
    return max(heights) if heights else 0


def _write_global_attributes(ds: nc.Dataset, domain, bbox):
    ds.Conventions = "CF-1.7"
    ds.origin_lat = float((bbox.south + bbox.north) / 2) if abs(bbox.south) <= 90 else 50.94
    ds.origin_lon = float((bbox.west + bbox.east) / 2) if abs(bbox.west) <= 180 else 6.96
    ds.origin_x = float(bbox.west)
    ds.origin_y = float(bbox.south)
    ds.origin_z = 0.0
    ds.palm_version = 23
    ds.origin_time = "2025-07-15 06:00:00 +02"
    ds.rotation_angle = 0.0


def _write_dimensions(ds: nc.Dataset, x_coords, y_coords, zlad):
    ds.createDimension("x", len(x_coords))
    ds.createDimension("y", len(y_coords))
    ds.createDimension("zlad", len(zlad))
    ds.createDimension("nsurface_fraction", 3)

    xv = ds.createVariable("x", "f4", ("x",))
    xv.units = "m"
    xv.axis = "X"
    xv[:] = x_coords

    yv = ds.createVariable("y", "f4", ("y",))
    yv.units = "m"
    yv.axis = "Y"
    yv[:] = y_coords

    zv = ds.createVariable("zlad", "f4", ("zlad",))
    zv.units = "m"
    zv[:] = zlad


def _write_terrain(ds: nc.Dataset, nx: int, ny: int):
    """Flat terrain (Phase 1 simplification). DEM integration in Phase 2."""
    zt = ds.createVariable("zt", "f4", ("y", "x"), fill_value=FILL_FLOAT)
    zt.units = "m"
    zt.long_name = "terrain height"
    zt[:, :] = 0.0  # flat terrain


def _write_surface_classification(ds, nx, ny, changes: list[SurfaceChange],
                                   bbox, dx, dy):
    """Write vegetation_type, pavement_type, water_type, surface_fraction."""
    veg_type = np.full((ny, nx), 3, dtype=np.int8)  # default: short grass
    pav_type = np.full((ny, nx), FILL_BYTE, dtype=np.int8)
    wat_type = np.full((ny, nx), FILL_BYTE, dtype=np.int8)

    # surface_fraction: [vegetation, pavement, water]
    sfrac = np.zeros((3, ny, nx), dtype=np.float32)
    sfrac[0, :, :] = 1.0  # default: all vegetation

    for change in changes:
        surf = get_surface(change.surface_type_id)
        poly = Polygon(change.vertices)
        cat = surf["palm_category"]
        type_id = surf["palm_type_id"]

        for iy in range(ny):
            for ix in range(nx):
                cx = bbox.west + (ix + 0.5) * dx
                cy = bbox.south + (iy + 0.5) * dy
                if poly.contains(Point(cx, cy)):
                    if cat == "vegetation":
                        veg_type[iy, ix] = type_id
                        sfrac[0, iy, ix] = 1.0
                        sfrac[1, iy, ix] = 0.0
                        sfrac[2, iy, ix] = 0.0
                    elif cat == "pavement":
                        pav_type[iy, ix] = type_id
                        veg_type[iy, ix] = FILL_BYTE
                        sfrac[0, iy, ix] = 0.0
                        sfrac[1, iy, ix] = 1.0
                        sfrac[2, iy, ix] = 0.0
                    elif cat == "water":
                        wat_type[iy, ix] = type_id
                        veg_type[iy, ix] = FILL_BYTE
                        sfrac[0, iy, ix] = 0.0
                        sfrac[1, iy, ix] = 0.0
                        sfrac[2, iy, ix] = 1.0

    v = ds.createVariable("vegetation_type", "b", ("y", "x"), fill_value=FILL_BYTE)
    v.long_name = "vegetation type"
    v[:, :] = veg_type

    p = ds.createVariable("pavement_type", "b", ("y", "x"), fill_value=FILL_BYTE)
    p.long_name = "pavement type"
    p[:, :] = pav_type

    w = ds.createVariable("water_type", "b", ("y", "x"), fill_value=FILL_BYTE)
    w.long_name = "water type"
    w[:, :] = wat_type

    sf = ds.createVariable("surface_fraction", "f4", ("nsurface_fraction", "y", "x"),
                           fill_value=FILL_FLOAT)
    sf.long_name = "surface fraction"
    sf[:, :, :] = sfrac


def _write_trees(ds, nx, ny, zlad, trees: list[TreePlacement], bbox, dx, dy, dz):
    """Write LAD array for placed trees."""
    lad = np.full((len(zlad), ny, nx), FILL_FLOAT, dtype=np.float32)

    for tree in trees:
        sp = get_species(tree.species_id)
        h = tree.height_m or sp["height_m"]["default"]
        crown_d = tree.crown_diameter_m or sp["crown_diameter_m"]["default"]
        trunk_h = sp["trunk_height_m"]["default"]
        lad_max = sp["lad_max_m2m3"]
        crown_r_cells = max(1, int(round((crown_d / 2) / dx)))

        # Grid position
        ix = int((tree.x - bbox.west) / dx)
        iy = int((tree.y - bbox.south) / dy)
        if not (0 <= ix < nx and 0 <= iy < ny):
            continue

        # Vertical LAD profile: zero in trunk, parabolic in crown
        for iz, z in enumerate(zlad):
            if z < trunk_h or z > h:
                continue
            crown_frac = 1.0 - ((z - (trunk_h + h) / 2) / ((h - trunk_h) / 2)) ** 2
            crown_frac = max(0.0, crown_frac)
            lad_at_z = lad_max * crown_frac

            for diy in range(-crown_r_cells, crown_r_cells + 1):
                for dix in range(-crown_r_cells, crown_r_cells + 1):
                    dist = np.sqrt(dix**2 + diy**2) * dx
                    if dist <= crown_d / 2:
                        jx = ix + dix
                        jy = iy + diy
                        if 0 <= jx < nx and 0 <= jy < ny:
                            existing = lad[iz, jy, jx]
                            val = lad_at_z * (1.0 - dist / (crown_d / 2))
                            if existing == FILL_FLOAT or existing < 0:
                                lad[iz, jy, jx] = val
                            else:
                                lad[iz, jy, jx] = max(existing, val)

    v = ds.createVariable("lad", "f4", ("zlad", "y", "x"), fill_value=FILL_FLOAT)
    v.units = "m2 m-3"
    v.long_name = "leaf area density"
    v[:, :, :] = lad


def _write_buildings(ds, nx, ny, dx, dy, bbox, domain, resolved):
    """Rasterise resolved buildings onto the PALM grid (ADR-004 §5).

    Produces three arrays:
    - buildings_2d:  building height in metres (FILL = no building)
    - building_id:   integer building ID per cell (FILL = no building)
    - building_type: PALM building type integer (FILL = no building)

    The rasterisation is deterministic: for each grid cell centre, we test
    which building polygon (if any) contains the point. If multiple
    buildings overlap a cell (shouldn't happen after validation), the
    tallest one wins. Geometry is projected to the domain's local metric
    CRS before point-in-polygon tests.
    """
    from shapely.geometry import Point as ShapelyPoint

    height_2d = np.full((ny, nx), FILL_FLOAT, dtype=np.float32)
    id_2d = np.full((ny, nx), FILL_INT, dtype=np.int32)
    type_2d = np.full((ny, nx), FILL_BYTE, dtype=np.int8)

    if not resolved:
        # Write empty arrays — no buildings
        _write_building_variables(ds, nx, ny, height_2d, id_2d, type_2d)
        return

    # Project building polygons to local metric CRS
    lon0, lat0 = _domain_centroid(domain)
    project = _project_factory(lon0, lat0)

    projected_buildings = []
    for idx, rb in enumerate(resolved):
        geom = rb.geometry
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            continue
        outer = geom["coordinates"][0]
        try:
            metric_coords = [project(lon, lat) for lon, lat in outer]
            poly = Polygon(metric_coords)
            if poly.is_valid:
                projected_buildings.append((idx + 1, poly, rb.height_m, rb))
        except Exception:
            continue

    if not projected_buildings:
        _write_building_variables(ds, nx, ny, height_2d, id_2d, type_2d)
        return

    # Project the domain origin
    origin_x, origin_y = project(bbox.west, bbox.south)

    # Rasterise: test each cell centre against all building polygons
    for iy in range(ny):
        cy = origin_y + (iy + 0.5) * dy
        for ix in range(nx):
            cx = origin_x + (ix + 0.5) * dx
            pt = ShapelyPoint(cx, cy)
            best_height = -1.0
            best_id = FILL_INT
            best_type = FILL_BYTE
            for bid, poly, h, rb in projected_buildings:
                if poly.contains(pt):
                    if h > best_height:
                        best_height = h
                        best_id = bid
                        # Derive PALM building type from roof + material
                        best_type = _derive_building_type(rb.roof_type, rb.wall_material_id)
            if best_height > 0:
                height_2d[iy, ix] = best_height
                id_2d[iy, ix] = best_id
                type_2d[iy, ix] = best_type

    _write_building_variables(ds, nx, ny, height_2d, id_2d, type_2d)


def _write_building_variables(ds, nx, ny, height_2d, id_2d, type_2d):
    """Write the three building NetCDF variables to the dataset."""
    b2d = ds.createVariable("buildings_2d", "f4", ("y", "x"), fill_value=FILL_FLOAT)
    b2d.long_name = "building height"
    b2d.units = "m"
    b2d[:, :] = height_2d

    bid = ds.createVariable("building_id", "i4", ("y", "x"), fill_value=FILL_INT)
    bid.long_name = "building id"
    bid[:, :] = id_2d

    btype = ds.createVariable("building_type", "b", ("y", "x"), fill_value=FILL_BYTE)
    btype.long_name = "building type"
    btype[:, :] = type_2d


# PALM building type derivation (simplified for v1).
# Full PALM building type catalogue is defined in palm_csd; we use
# a minimal mapping based on wall material and roof type.
_BUILDING_TYPE_MAP = {
    ("concrete", "flat"): 3,   # office/commercial, flat roof
    ("concrete", "pitched"): 4,
    ("brick", "flat"): 1,      # residential, flat roof
    ("brick", "pitched"): 2,   # residential, pitched
    ("glass", "flat"): 5,      # modern commercial
    ("steel", "flat"): 6,      # industrial
    ("wood", "pitched"): 7,    # traditional
    ("stone", "flat"): 1,
}

_DEFAULT_BUILDING_TYPE = 1  # generic residential


def _derive_building_type(roof_type: str | None, wall_material_id: str | None) -> np.int8:
    key = (wall_material_id or "concrete", roof_type or "flat")
    return np.int8(_BUILDING_TYPE_MAP.get(key, _DEFAULT_BUILDING_TYPE))
