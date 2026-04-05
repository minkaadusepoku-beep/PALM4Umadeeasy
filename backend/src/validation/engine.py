"""
Validation engine: catch invalid scenarios before they reach PALM.

Performs spatial, physical, resource, and data quality checks.
Returns structured validation results with severity levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from shapely.geometry import Polygon, Point

from ..models.scenario import (
    Scenario, ComparisonRequest, TreePlacement, SurfaceChange,
    GreenRoof, DataQualityTier,
)
from ..catalogues.loader import get_species, get_surface


class Severity(str, Enum):
    ERROR = "error"       # blocks execution
    WARNING = "warning"   # proceeds with caveat
    INFO = "info"         # informational


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    context: Optional[dict] = None


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]


def validate_scenario(scenario: Scenario) -> ValidationResult:
    """Run all validation checks on a scenario."""
    issues: list[ValidationIssue] = []

    issues.extend(_check_domain(scenario))
    issues.extend(_check_trees(scenario))
    issues.extend(_check_surfaces(scenario))
    issues.extend(_check_green_roofs(scenario))
    issues.extend(_check_simulation(scenario))
    issues.extend(_check_resource_limits(scenario))
    issues.extend(_check_data_quality(scenario))

    has_errors = any(i.severity == Severity.ERROR for i in issues)
    return ValidationResult(valid=not has_errors, issues=issues)


def validate_comparison(request: ComparisonRequest) -> ValidationResult:
    """Validate a comparison request (both scenarios + compatibility)."""
    issues: list[ValidationIssue] = []

    baseline_result = validate_scenario(request.baseline)
    intervention_result = validate_scenario(request.intervention)

    for issue in baseline_result.issues:
        issue.code = f"baseline.{issue.code}"
        issues.append(issue)
    for issue in intervention_result.issues:
        issue.code = f"intervention.{issue.code}"
        issues.append(issue)

    # Domains must match for comparison
    b = request.baseline.domain
    i = request.intervention.domain
    if b.bbox != i.bbox:
        issues.append(ValidationIssue(
            code="comparison.domain_mismatch",
            severity=Severity.ERROR,
            message="Baseline and intervention must share the same domain bounding box.",
        ))
    if b.resolution_m != i.resolution_m:
        issues.append(ValidationIssue(
            code="comparison.resolution_mismatch",
            severity=Severity.ERROR,
            message="Baseline and intervention must use the same grid resolution.",
        ))
    if request.baseline.simulation.forcing != request.intervention.simulation.forcing:
        issues.append(ValidationIssue(
            code="comparison.forcing_mismatch",
            severity=Severity.WARNING,
            message="Baseline and intervention use different forcing archetypes. "
                    "Comparison results may reflect forcing differences rather than interventions.",
        ))

    has_errors = any(i.severity == Severity.ERROR for i in issues)
    return ValidationResult(valid=not has_errors, issues=issues)


# --- Domain checks ---

def _check_domain(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    d = scenario.domain
    bbox = d.bbox

    # Minimum domain size: 10x10 cells
    if d.nx < 10:
        issues.append(ValidationIssue(
            code="domain.too_narrow",
            severity=Severity.ERROR,
            message=f"Domain width {d.nx} cells is below minimum (10). "
                    f"Increase domain extent or decrease resolution.",
            context={"nx": d.nx, "resolution_m": d.resolution_m},
        ))
    if d.ny < 10:
        issues.append(ValidationIssue(
            code="domain.too_short",
            severity=Severity.ERROR,
            message=f"Domain height {d.ny} cells is below minimum (10). "
                    f"Increase domain extent or decrease resolution.",
            context={"ny": d.ny, "resolution_m": d.resolution_m},
        ))

    # Maximum domain size: 500x500 cells (resource guard)
    if d.nx > 500 or d.ny > 500:
        issues.append(ValidationIssue(
            code="domain.too_large",
            severity=Severity.ERROR,
            message=f"Domain {d.nx}x{d.ny} cells exceeds maximum (500x500). "
                    f"Reduce extent or increase resolution.",
            context={"nx": d.nx, "ny": d.ny},
        ))

    # Grid dimensions should be even (FFTW performance)
    if d.nx % 2 != 0:
        issues.append(ValidationIssue(
            code="domain.odd_nx",
            severity=Severity.WARNING,
            message=f"nx={d.nx} is odd. Even grid dimensions improve FFT performance.",
        ))
    if d.ny % 2 != 0:
        issues.append(ValidationIssue(
            code="domain.odd_ny",
            severity=Severity.WARNING,
            message=f"ny={d.ny} is odd. Even grid dimensions improve FFT performance.",
        ))

    # Domain height check
    domain_height = d.nz * d.dz
    if domain_height < 50:
        issues.append(ValidationIssue(
            code="domain.low_ceiling",
            severity=Severity.WARNING,
            message=f"Domain height {domain_height:.0f}m may be insufficient. "
                    f"Recommend at least 50m for urban canopy flows.",
        ))

    return issues


# --- Tree checks ---

def _check_trees(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    bbox = scenario.domain.bbox

    for idx, tree in enumerate(scenario.trees):
        prefix = f"tree[{idx}]"

        # Species exists in catalogue
        try:
            sp = get_species(tree.species_id)
        except KeyError as e:
            issues.append(ValidationIssue(
                code=f"{prefix}.unknown_species",
                severity=Severity.ERROR,
                message=str(e),
            ))
            continue

        # Tree within domain
        if not (bbox.west <= tree.x <= bbox.east and bbox.south <= tree.y <= bbox.north):
            issues.append(ValidationIssue(
                code=f"{prefix}.outside_domain",
                severity=Severity.ERROR,
                message=f"Tree at ({tree.x}, {tree.y}) is outside domain bounds.",
            ))

        # Height plausibility
        if tree.height_m:
            max_h = sp["height_m"]["max"]
            if tree.height_m > max_h:
                issues.append(ValidationIssue(
                    code=f"{prefix}.height_exceeds_species_max",
                    severity=Severity.WARNING,
                    message=f"Height {tree.height_m}m exceeds species maximum ({max_h}m) "
                            f"for {tree.species_id}.",
                ))

        # Crown diameter plausibility
        if tree.crown_diameter_m:
            max_cd = sp["crown_diameter_m"]["max"]
            if tree.crown_diameter_m > max_cd:
                issues.append(ValidationIssue(
                    code=f"{prefix}.crown_exceeds_species_max",
                    severity=Severity.WARNING,
                    message=f"Crown diameter {tree.crown_diameter_m}m exceeds species maximum "
                            f"({max_cd}m) for {tree.species_id}.",
                ))

        # Crown must fit in domain
        h = tree.height_m or sp["height_m"]["default"]
        cd = tree.crown_diameter_m or sp["crown_diameter_m"]["default"]
        cr = cd / 2
        if (tree.x - cr < bbox.west or tree.x + cr > bbox.east or
                tree.y - cr < bbox.south or tree.y + cr > bbox.north):
            issues.append(ValidationIssue(
                code=f"{prefix}.crown_extends_outside_domain",
                severity=Severity.WARNING,
                message=f"Crown of tree at ({tree.x}, {tree.y}) extends beyond domain. "
                        f"LAD will be clipped at boundary.",
            ))

    # Tree overlap check (simplified: pairwise distance)
    for i in range(len(scenario.trees)):
        for j in range(i + 1, len(scenario.trees)):
            t1, t2 = scenario.trees[i], scenario.trees[j]
            try:
                sp1 = get_species(t1.species_id)
                sp2 = get_species(t2.species_id)
            except KeyError:
                continue
            cd1 = t1.crown_diameter_m or sp1["crown_diameter_m"]["default"]
            cd2 = t2.crown_diameter_m or sp2["crown_diameter_m"]["default"]
            dist = ((t1.x - t2.x) ** 2 + (t1.y - t2.y) ** 2) ** 0.5
            min_dist = (cd1 + cd2) / 2 * 0.5  # allow 50% overlap
            if dist < min_dist:
                issues.append(ValidationIssue(
                    code=f"tree[{i}].overlap_tree[{j}]",
                    severity=Severity.WARNING,
                    message=f"Trees {i} and {j} are {dist:.1f}m apart (min recommended: "
                            f"{min_dist:.1f}m). Overlapping crowns will use maximum LAD.",
                ))

    return issues


# --- Surface checks ---

def _check_surfaces(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    bbox = scenario.domain.bbox
    domain_poly = Polygon([
        (bbox.west, bbox.south), (bbox.east, bbox.south),
        (bbox.east, bbox.north), (bbox.west, bbox.north),
    ])

    for idx, sc in enumerate(scenario.surface_changes):
        prefix = f"surface[{idx}]"

        # Surface type exists
        try:
            get_surface(sc.surface_type_id)
        except KeyError as e:
            issues.append(ValidationIssue(
                code=f"{prefix}.unknown_surface",
                severity=Severity.ERROR,
                message=str(e),
            ))

        # Valid polygon
        try:
            poly = Polygon(sc.vertices)
            if not poly.is_valid:
                issues.append(ValidationIssue(
                    code=f"{prefix}.invalid_polygon",
                    severity=Severity.ERROR,
                    message="Surface polygon is geometrically invalid (self-intersecting).",
                ))
                continue
        except Exception:
            issues.append(ValidationIssue(
                code=f"{prefix}.invalid_vertices",
                severity=Severity.ERROR,
                message="Cannot construct polygon from provided vertices.",
            ))
            continue

        # Polygon inside domain
        if not domain_poly.contains(poly):
            if domain_poly.intersects(poly):
                issues.append(ValidationIssue(
                    code=f"{prefix}.partially_outside_domain",
                    severity=Severity.WARNING,
                    message="Surface polygon extends beyond domain. Will be clipped.",
                ))
            else:
                issues.append(ValidationIssue(
                    code=f"{prefix}.outside_domain",
                    severity=Severity.ERROR,
                    message="Surface polygon is entirely outside domain bounds.",
                ))

        # Area too small to resolve
        area = poly.area
        cell_area = scenario.domain.resolution_m ** 2
        if area < cell_area:
            issues.append(ValidationIssue(
                code=f"{prefix}.too_small",
                severity=Severity.WARNING,
                message=f"Surface area {area:.1f}m2 is smaller than one grid cell "
                        f"({cell_area:.0f}m2). May not appear in output.",
            ))

    return issues


# --- Green roof checks ---

def _check_green_roofs(scenario: Scenario) -> list[ValidationIssue]:
    issues = []

    if scenario.green_roofs:
        issues.append(ValidationIssue(
            code="green_roof.not_implemented",
            severity=Severity.WARNING,
            message="Green roof translation is not yet implemented (Phase 2). "
                    "Green roofs in this scenario will be ignored in PALM input generation.",
        ))

    for idx, gr in enumerate(scenario.green_roofs):
        prefix = f"green_roof[{idx}]"

        if not gr.building_id:
            issues.append(ValidationIssue(
                code=f"{prefix}.no_building_id",
                severity=Severity.ERROR,
                message="Green roof must reference a building ID.",
            ))

        if gr.vegetation_type not in ("sedum", "extensive", "intensive", "grass"):
            issues.append(ValidationIssue(
                code=f"{prefix}.unknown_vegetation_type",
                severity=Severity.WARNING,
                message=f"Vegetation type '{gr.vegetation_type}' is not standard. "
                        f"Expected: sedum, extensive, intensive, grass.",
            ))

    return issues


# --- Simulation checks ---

def _check_simulation(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    sim = scenario.simulation

    # Output interval vs simulation length
    total_seconds = sim.simulation_hours * 3600
    if sim.output_interval_s > total_seconds:
        issues.append(ValidationIssue(
            code="simulation.interval_exceeds_runtime",
            severity=Severity.ERROR,
            message=f"Output interval ({sim.output_interval_s}s) exceeds total simulation "
                    f"time ({total_seconds:.0f}s). No output would be produced.",
        ))

    # Very short simulations may not reach thermal equilibrium
    if sim.simulation_hours < 2.0:
        issues.append(ValidationIssue(
            code="simulation.short_runtime",
            severity=Severity.WARNING,
            message="Simulation under 2 hours may not reach thermal equilibrium.",
        ))

    return issues


# --- Resource limit checks ---

def _check_resource_limits(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    d = scenario.domain
    total_cells = d.nx * d.ny * d.nz

    # Estimated memory: ~200 bytes per cell (conservative for LES)
    est_memory_gb = total_cells * 200 / (1024 ** 3)

    if total_cells > 50_000_000:
        issues.append(ValidationIssue(
            code="resources.excessive_cells",
            severity=Severity.ERROR,
            message=f"Domain has {total_cells:,} cells (max 50M). "
                    f"Estimated memory: {est_memory_gb:.1f} GB.",
            context={"total_cells": total_cells, "est_memory_gb": round(est_memory_gb, 1)},
        ))
    elif total_cells > 10_000_000:
        issues.append(ValidationIssue(
            code="resources.large_domain",
            severity=Severity.WARNING,
            message=f"Domain has {total_cells:,} cells. "
                    f"Estimated memory: {est_memory_gb:.1f} GB. May require large VM.",
            context={"total_cells": total_cells, "est_memory_gb": round(est_memory_gb, 1)},
        ))

    # Estimated runtime: ~1 CPU-hour per 1M cells per simulation hour
    n_trees = len(scenario.trees)
    hours = scenario.simulation.simulation_hours
    est_cpu_hours = (total_cells / 1_000_000) * hours * (1 + n_trees * 0.01)
    if est_cpu_hours > 100:
        issues.append(ValidationIssue(
            code="resources.long_runtime",
            severity=Severity.WARNING,
            message=f"Estimated runtime: ~{est_cpu_hours:.0f} CPU-hours. "
                    f"Consider reducing domain size or simulation duration.",
            context={"est_cpu_hours": round(est_cpu_hours, 1)},
        ))

    return issues


# --- Data quality checks ---

def _check_data_quality(scenario: Scenario) -> list[ValidationIssue]:
    issues = []
    tier = scenario.effective_data_tier

    if tier == DataQualityTier.SCREENING:
        issues.append(ValidationIssue(
            code="data_quality.screening_tier",
            severity=Severity.INFO,
            message="Effective data quality: SCREENING. Results are indicative only. "
                    "Not suitable for regulatory submission without higher-quality inputs.",
        ))

    # Check individual source tiers
    ds = scenario.data_sources
    if ds.buildings.quality_tier == DataQualityTier.SCREENING:
        issues.append(ValidationIssue(
            code="data_quality.buildings_screening",
            severity=Severity.INFO,
            message=f"Building data source '{ds.buildings.source_type}' is screening-tier. "
                    f"Building heights and shapes may be approximate.",
        ))

    return issues
