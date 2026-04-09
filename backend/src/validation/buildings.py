"""
Building geometry edit validation (ADR-004 §4).

Eight blocking rules. No "warn and accept" path. Geometry is stored in WGS84
GeoJSON; metric checks are run in a local equirectangular projection
centred on the project domain centroid. For PALM-scale domains (typically
<2 km wide) this is sub-metre accurate, which is well below the validator
tolerances.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity

from ..models.scenario import (
    BuildingEdit,
    BuildingEditAdd,
    BuildingEditModify,
    BuildingEditRemove,
    BuildingsEdits,
    DataQualityTier,
    DomainConfig,
    Scenario,
)

# ADR-004 §11.1, §11.2
MIN_BUILDING_AREA_M2 = 9.0
OVERLAP_TOLERANCE_M = 0.5
HEIGHT_MIN_M = 2.0
HEIGHT_MAX_M = 300.0
HEIGHT_SOFT_WARN_M = 80.0
GHOST_CELL_LAYERS = 1

# ADR-004 §11.4
LARGE_BUILDING_HEIGHT_M = 30.0
LARGE_BUILDING_AREA_M2 = 1000.0


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class BuildingValidationError:
    edit_id: Optional[str]
    code: str
    message: str


@dataclass
class BuildingValidationResult:
    valid: bool
    errors: list[BuildingValidationError]
    warnings: list[BuildingValidationError]


# ---------------------------------------------------------------------------
# Local metric projection (equirectangular at domain centroid)
# ---------------------------------------------------------------------------

R_EARTH = 6378137.0  # metres, WGS84 equatorial radius


def _project_factory(lon0: float, lat0: float):
    cos_lat0 = math.cos(math.radians(lat0))

    def to_metric(lon: float, lat: float) -> tuple[float, float]:
        x = math.radians(lon - lon0) * R_EARTH * cos_lat0
        y = math.radians(lat - lat0) * R_EARTH
        return x, y

    return to_metric


def _polygon_from_geojson_metric(geom: dict, project) -> Polygon:
    if geom.get("type") != "Polygon":
        raise ValueError(f"unsupported geometry type {geom.get('type')!r}; expected Polygon")
    coords = geom.get("coordinates")
    if not coords or not coords[0]:
        raise ValueError("polygon has no coordinates")
    outer = coords[0]
    if len(outer) < 4:
        raise ValueError("polygon outer ring has fewer than 4 coordinates")
    if outer[0] != outer[-1]:
        raise ValueError("polygon outer ring is not closed")
    metric = [project(lon, lat) for lon, lat in outer]
    return Polygon(metric)


def _domain_centroid(domain: DomainConfig) -> tuple[float, float]:
    bbox = domain.bbox
    return ((bbox.west + bbox.east) / 2.0, (bbox.south + bbox.north) / 2.0)


def _domain_polygon_metric(domain: DomainConfig, project) -> Polygon:
    bbox = domain.bbox
    margin_m = GHOST_CELL_LAYERS * domain.resolution_m
    p = [
        project(bbox.west, bbox.south),
        project(bbox.east, bbox.south),
        project(bbox.east, bbox.north),
        project(bbox.west, bbox.north),
    ]
    poly = Polygon(p)
    # Shrink inward by `margin_m` so a ring of ghost cells stays clear.
    return poly.buffer(-margin_m) if margin_m > 0 else poly


# ---------------------------------------------------------------------------
# Snapshot resolution
# ---------------------------------------------------------------------------

@dataclass
class ResolvedBuilding:
    """A building after applying the edit chain to the base snapshot."""
    building_id: str
    geometry: dict           # WGS84 GeoJSON Polygon
    height_m: float
    roof_type: str = "flat"
    wall_material_id: Optional[str] = None
    source: str = "base"     # "base" or "edit"


def resolve_buildings(
    base_buildings: list[dict],
    edits: Optional[BuildingsEdits],
) -> list[ResolvedBuilding]:
    """
    Apply the edit chain in order to a base building set.

    `base_buildings` is a list of dicts shaped like
    `{"id": str, "geometry": GeoJSON, "height_m": float, ...}`.

    The result is the deterministic post-edit building set. Validation is
    NOT performed here — call `validate_buildings_edits` for that.
    """
    by_id: dict[str, ResolvedBuilding] = {}
    for b in base_buildings:
        rb = ResolvedBuilding(
            building_id=str(b["id"]),
            geometry=b["geometry"],
            height_m=float(b.get("height_m", 10.0)),
            roof_type=b.get("roof_type", "flat"),
            wall_material_id=b.get("wall_material_id"),
            source="base",
        )
        by_id[rb.building_id] = rb

    if edits is None:
        return list(by_id.values())

    for e in edits.edits:
        if isinstance(e, BuildingEditAdd):
            new_id = f"edit:{e.id}"
            by_id[new_id] = ResolvedBuilding(
                building_id=new_id,
                geometry=e.geometry,
                height_m=e.height_m,
                roof_type=e.roof_type.value,
                wall_material_id=e.wall_material_id,
                source="edit",
            )
        elif isinstance(e, BuildingEditModify):
            target = by_id.get(e.target_building_id)
            if target is None:
                # Reference integrity is enforced by the validator; resolution
                # is permissive so the validator can report the exact error.
                continue
            for k, v in e.set.items():
                if hasattr(target, k):
                    setattr(target, k, v)
        elif isinstance(e, BuildingEditRemove):
            by_id.pop(e.target_building_id, None)

    return list(by_id.values())


# ---------------------------------------------------------------------------
# Validation contract (ADR-004 §4)
# ---------------------------------------------------------------------------

def validate_buildings_edits(
    scenario: Scenario,
    base_buildings: list[dict],
) -> BuildingValidationResult:
    """
    Run all eight rules from ADR-004 §4 against `scenario.buildings_edits`.

    `base_buildings` is the materialised base snapshot identified by
    `scenario.buildings_edits.base_snapshot_id`. Loading the snapshot is
    the caller's responsibility — this keeps the validator pure and
    testable.
    """
    errors: list[BuildingValidationError] = []
    warnings: list[BuildingValidationError] = []

    edits_obj = scenario.buildings_edits
    if edits_obj is None or not edits_obj.edits:
        return BuildingValidationResult(valid=True, errors=[], warnings=[])

    domain = scenario.domain
    lon0, lat0 = _domain_centroid(domain)
    project = _project_factory(lon0, lat0)

    domain_poly_m = _domain_polygon_metric(domain, project)
    min_edge_m = 2.0 * domain.resolution_m

    # Bootstrap the working set: project all base buildings to metric.
    by_id: dict[str, dict] = {}
    for b in base_buildings:
        try:
            poly_m = _polygon_from_geojson_metric(b["geometry"], project)
        except Exception:
            continue
        by_id[str(b["id"])] = {
            "polygon_m": poly_m,
            "height_m": float(b.get("height_m", 10.0)),
            "source": "base",
        }

    seen_edit_ids: set[str] = set()

    for e in edits_obj.edits:
        eid = e.id

        # Rule 8 piece: ids must be unique within the chain.
        if eid in seen_edit_ids:
            errors.append(BuildingValidationError(
                edit_id=eid, code="edit.duplicate_id",
                message=f"Edit id {eid!r} appears more than once.",
            ))
            continue
        seen_edit_ids.add(eid)

        if isinstance(e, BuildingEditAdd):
            _validate_add(e, project, domain_poly_m, min_edge_m, by_id, errors, warnings)

        elif isinstance(e, BuildingEditModify):
            _validate_modify(e, by_id, errors, warnings)

        elif isinstance(e, BuildingEditRemove):
            if e.target_building_id not in by_id:
                errors.append(BuildingValidationError(
                    edit_id=eid, code="remove.unknown_target",
                    message=f"remove targets unknown building {e.target_building_id!r}.",
                ))
            else:
                by_id.pop(e.target_building_id)

    return BuildingValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def _validate_add(
    e: BuildingEditAdd,
    project,
    domain_poly_m: Polygon,
    min_edge_m: float,
    by_id: dict[str, dict],
    errors: list[BuildingValidationError],
    warnings: list[BuildingValidationError],
) -> None:
    eid = e.id

    # Rule 1: well-formed polygon.
    try:
        poly_m = _polygon_from_geojson_metric(e.geometry, project)
    except Exception as exc:
        errors.append(BuildingValidationError(
            edit_id=eid, code="add.invalid_geometry",
            message=f"add[{eid}] geometry is invalid: {exc}",
        ))
        return

    if not poly_m.is_valid:
        errors.append(BuildingValidationError(
            edit_id=eid, code="add.invalid_geometry",
            message=f"add[{eid}] polygon is not valid: {explain_validity(poly_m)}",
        ))
        return

    # Rule 2: footprint area.
    if poly_m.area < MIN_BUILDING_AREA_M2:
        errors.append(BuildingValidationError(
            edit_id=eid, code="add.area_too_small",
            message=f"add[{eid}] footprint {poly_m.area:.1f} m² is below "
                    f"minimum {MIN_BUILDING_AREA_M2} m².",
        ))
        return

    # Rule 3: minimum edge length.
    coords = list(poly_m.exterior.coords)
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        edge = math.hypot(x2 - x1, y2 - y1)
        if edge < min_edge_m:
            errors.append(BuildingValidationError(
                edit_id=eid, code="add.edge_too_short",
                message=f"add[{eid}] edge {i} is {edge:.2f} m, "
                        f"below 2*dx ({min_edge_m:.2f} m).",
            ))
            return

    # Rule 4: height bounds (already partly enforced by pydantic).
    if e.height_m < HEIGHT_MIN_M or e.height_m > HEIGHT_MAX_M:
        errors.append(BuildingValidationError(
            edit_id=eid, code="add.height_out_of_range",
            message=f"add[{eid}] height {e.height_m} m outside "
                    f"[{HEIGHT_MIN_M}, {HEIGHT_MAX_M}].",
        ))
        return
    if e.height_m > HEIGHT_SOFT_WARN_M:
        warnings.append(BuildingValidationError(
            edit_id=eid, code="add.height_above_soft_warn",
            message=f"add[{eid}] height {e.height_m} m exceeds "
                    f"{HEIGHT_SOFT_WARN_M} m soft warning threshold.",
        ))

    # Rule 5: inside the project domain (with ghost-cell margin).
    if not domain_poly_m.contains(poly_m):
        errors.append(BuildingValidationError(
            edit_id=eid, code="add.outside_domain",
            message=f"add[{eid}] polygon is not fully inside the project "
                    f"domain (with one-cell ghost margin).",
        ))
        return

    # Rule 6: no overlap with existing buildings.
    shrunk = poly_m.buffer(-OVERLAP_TOLERANCE_M)
    for other_id, other in by_id.items():
        other_shrunk = other["polygon_m"].buffer(-OVERLAP_TOLERANCE_M)
        if shrunk.intersects(other_shrunk):
            errors.append(BuildingValidationError(
                edit_id=eid, code="add.overlap",
                message=f"add[{eid}] overlaps existing building {other_id}.",
            ))
            return

    # Accept and add to the working set under a synthetic id.
    new_id = f"edit:{eid}"
    by_id[new_id] = {"polygon_m": poly_m, "height_m": e.height_m, "source": "edit"}


def _validate_modify(
    e: BuildingEditModify,
    by_id: dict[str, dict],
    errors: list[BuildingValidationError],
    warnings: list[BuildingValidationError],
) -> None:
    target = by_id.get(e.target_building_id)
    if target is None:
        errors.append(BuildingValidationError(
            edit_id=e.id, code="modify.unknown_target",
            message=f"modify targets unknown building {e.target_building_id!r}.",
        ))
        return

    if "height_m" in e.set:
        try:
            new_h = float(e.set["height_m"])
        except (TypeError, ValueError):
            errors.append(BuildingValidationError(
                edit_id=e.id, code="modify.height_not_number",
                message=f"modify[{e.id}] height_m is not a number.",
            ))
            return
        if new_h < HEIGHT_MIN_M or new_h > HEIGHT_MAX_M:
            errors.append(BuildingValidationError(
                edit_id=e.id, code="modify.height_out_of_range",
                message=f"modify[{e.id}] height {new_h} m outside "
                        f"[{HEIGHT_MIN_M}, {HEIGHT_MAX_M}].",
            ))
            return
        if new_h > HEIGHT_SOFT_WARN_M:
            warnings.append(BuildingValidationError(
                edit_id=e.id, code="modify.height_above_soft_warn",
                message=f"modify[{e.id}] height {new_h} m exceeds "
                        f"{HEIGHT_SOFT_WARN_M} m soft warning threshold.",
            ))
        target["height_m"] = new_h


# ---------------------------------------------------------------------------
# Provenance downgrade (ADR-004 §6)
# ---------------------------------------------------------------------------

def downgraded_buildings_tier(
    base_tier: DataQualityTier,
    scenario: Scenario,
    base_buildings: Optional[list[dict]] = None,
) -> DataQualityTier:
    """
    Apply the ADR-004 §6 downgrade rules to the buildings data quality tier.

    The DataQualityTier enum exposes SCREENING < PROJECT < RESEARCH. ADR-004
    speaks of AUTHORITATIVE / PROFESSIONAL — those map onto RESEARCH /
    PROJECT respectively in this codebase. The mapping is:

      0 edits             -> unchanged
      ≥1 edit             -> at most PROJECT (never RESEARCH)
      ≥1 large add        -> at most SCREENING
    """
    edits_obj = scenario.buildings_edits
    if edits_obj is None or not edits_obj.edits:
        return base_tier

    has_large_add = False
    project = None
    if base_buildings is not None:
        lon0, lat0 = _domain_centroid(scenario.domain)
        project = _project_factory(lon0, lat0)

    for e in edits_obj.edits:
        if isinstance(e, BuildingEditAdd):
            if e.height_m > LARGE_BUILDING_HEIGHT_M:
                has_large_add = True
                break
            if project is not None:
                try:
                    poly_m = _polygon_from_geojson_metric(e.geometry, project)
                    if poly_m.area > LARGE_BUILDING_AREA_M2:
                        has_large_add = True
                        break
                except Exception:
                    pass

    if has_large_add:
        return DataQualityTier.SCREENING

    # Cap at PROJECT.
    order = [DataQualityTier.SCREENING, DataQualityTier.PROJECT, DataQualityTier.RESEARCH]
    if order.index(base_tier) > order.index(DataQualityTier.PROJECT):
        return DataQualityTier.PROJECT
    return base_tier
