"""
Comparison engine: compute deltas between baseline and intervention.

Core differentiator of PALM4Umadeeasy — every scenario is meaningless
without a reference. Produces difference grids, delta statistics,
threshold impact analysis, and ranked improvements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .engine import PostProcessingResult, ComfortStatistics
from ..catalogues.loader import classify_pet


@dataclass
class DeltaField:
    """Difference grid: intervention minus baseline for one variable."""
    variable: str
    units: str
    data: np.ndarray  # shape (ny, nx), negative = improvement for heat metrics
    time_averaged: bool = True


@dataclass
class DeltaStatistics:
    """Statistics of the difference grid."""
    variable: str
    mean_delta: float
    median_delta: float
    max_improvement: float  # most negative for heat metrics
    max_worsening: float    # most positive for heat metrics
    pct_improved: float     # fraction of cells that improved
    pct_worsened: float
    pct_unchanged: float    # within ±0.5 tolerance
    n_valid: int


@dataclass
class ThresholdImpact:
    """How many cells cross a comfort threshold due to intervention."""
    variable: str
    threshold_name: str
    threshold_value: float
    cells_above_baseline: int
    cells_above_intervention: int
    cells_improved: int      # crossed from above to below threshold
    cells_worsened: int      # crossed from below to above threshold
    pct_improved: float


@dataclass
class RankedImprovement:
    """Spatial region where the intervention had the largest effect."""
    variable: str
    region_description: str
    mean_delta: float
    area_m2: float


@dataclass
class ComparisonResult:
    """Complete comparison between baseline and intervention."""
    baseline_name: str
    intervention_name: str
    delta_fields: dict[str, DeltaField]
    delta_statistics: dict[str, DeltaStatistics]
    threshold_impacts: list[ThresholdImpact]
    ranked_improvements: list[RankedImprovement]
    baseline_stats: dict[str, ComfortStatistics]
    intervention_stats: dict[str, ComfortStatistics]
    metadata: dict = field(default_factory=dict)


# PET thresholds for impact analysis (VDI 3787)
PET_THRESHOLDS = [
    ("No thermal stress", 23.0),
    ("Moderate heat stress", 29.0),
    ("Strong heat stress", 35.0),
    ("Extreme heat stress", 41.0),
]

DELTA_TOLERANCE = 0.5  # ±0.5°C considered "unchanged"


def compare_scenarios(
    baseline: PostProcessingResult,
    intervention: PostProcessingResult,
    resolution_m: float = 10.0,
) -> ComparisonResult:
    """
    Compare two post-processing results and produce difference analysis.

    Convention: delta = intervention - baseline.
    For heat metrics (PET, UTCI, MRT, Tsurf), negative delta = improvement.
    """
    delta_fields = {}
    delta_statistics = {}
    threshold_impacts = []
    ranked_improvements = []

    # Find common variables
    common_vars = set(baseline.fields.keys()) & set(intervention.fields.keys())

    for var_name in common_vars:
        b_fields = baseline.fields[var_name]
        i_fields = intervention.fields[var_name]

        # Time-average both
        b_mean = np.nanmean(np.stack([f.data for f in b_fields], axis=0), axis=0)
        i_mean = np.nanmean(np.stack([f.data for f in i_fields], axis=0), axis=0)

        # Ensure same shape
        if b_mean.shape != i_mean.shape:
            continue

        delta = i_mean - b_mean

        # Mask where either is NaN
        valid_mask = ~(np.isnan(b_mean) | np.isnan(i_mean))
        delta_valid = delta[valid_mask]

        if len(delta_valid) == 0:
            continue

        units = b_fields[0].units
        delta_fields[var_name] = DeltaField(
            variable=var_name,
            units=units,
            data=delta,
        )

        # Delta statistics
        improved = delta_valid < -DELTA_TOLERANCE
        worsened = delta_valid > DELTA_TOLERANCE
        unchanged = ~improved & ~worsened
        n = len(delta_valid)

        delta_statistics[var_name] = DeltaStatistics(
            variable=var_name,
            mean_delta=float(np.mean(delta_valid)),
            median_delta=float(np.median(delta_valid)),
            max_improvement=float(np.min(delta_valid)),
            max_worsening=float(np.max(delta_valid)),
            pct_improved=float(np.sum(improved) / n) if n > 0 else 0.0,
            pct_worsened=float(np.sum(worsened) / n) if n > 0 else 0.0,
            pct_unchanged=float(np.sum(unchanged) / n) if n > 0 else 0.0,
            n_valid=n,
        )

        # PET threshold impact analysis
        if var_name == "bio_pet*":
            for thresh_name, thresh_val in PET_THRESHOLDS:
                b_above = np.sum(b_mean[valid_mask] > thresh_val)
                i_above = np.sum(i_mean[valid_mask] > thresh_val)
                improved_cells = np.sum(
                    (b_mean[valid_mask] > thresh_val) & (i_mean[valid_mask] <= thresh_val)
                )
                worsened_cells = np.sum(
                    (b_mean[valid_mask] <= thresh_val) & (i_mean[valid_mask] > thresh_val)
                )
                threshold_impacts.append(ThresholdImpact(
                    variable=var_name,
                    threshold_name=thresh_name,
                    threshold_value=thresh_val,
                    cells_above_baseline=int(b_above),
                    cells_above_intervention=int(i_above),
                    cells_improved=int(improved_cells),
                    cells_worsened=int(worsened_cells),
                    pct_improved=float(improved_cells / n) if n > 0 else 0.0,
                ))

        # Ranked improvements: find region of maximum cooling
        ranked_improvements.extend(
            _find_improvement_regions(var_name, delta, valid_mask, resolution_m)
        )

    return ComparisonResult(
        baseline_name=baseline.case_name,
        intervention_name=intervention.case_name,
        delta_fields=delta_fields,
        delta_statistics=delta_statistics,
        threshold_impacts=threshold_impacts,
        ranked_improvements=ranked_improvements,
        baseline_stats=baseline.statistics,
        intervention_stats=intervention.statistics,
        metadata={
            "delta_tolerance": DELTA_TOLERANCE,
            "convention": "delta = intervention - baseline; negative = improvement for heat",
        },
    )


def _find_improvement_regions(
    var_name: str, delta: np.ndarray, valid_mask: np.ndarray,
    resolution_m: float, n_regions: int = 3,
) -> list[RankedImprovement]:
    """Find the N regions with the largest improvement (most negative delta)."""
    results = []

    # Simple approach: divide domain into quadrants and rank
    ny, nx = delta.shape
    mid_y, mid_x = ny // 2, nx // 2
    quadrants = [
        ("NW quadrant", slice(mid_y, ny), slice(0, mid_x)),
        ("NE quadrant", slice(mid_y, ny), slice(mid_x, nx)),
        ("SW quadrant", slice(0, mid_y), slice(0, mid_x)),
        ("SE quadrant", slice(0, mid_y), slice(mid_x, nx)),
    ]

    quad_deltas = []
    for name, sy, sx in quadrants:
        region = delta[sy, sx]
        mask = valid_mask[sy, sx]
        if np.sum(mask) > 0:
            mean_d = float(np.nanmean(region[mask]))
            area = float(np.sum(mask)) * resolution_m ** 2
            quad_deltas.append((name, mean_d, area))

    # Sort by mean delta (most negative first = most improved)
    quad_deltas.sort(key=lambda x: x[1])

    for name, mean_d, area in quad_deltas[:n_regions]:
        results.append(RankedImprovement(
            variable=var_name,
            region_description=name,
            mean_delta=mean_d,
            area_m2=area,
        ))

    return results
