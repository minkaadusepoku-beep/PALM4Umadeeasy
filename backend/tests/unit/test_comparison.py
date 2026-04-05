"""
Unit tests for comparison engine: hand-computed delta verification.

These tests construct known grids and assert exact delta values,
verifying the comparison logic independent of the stub runner.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.postprocessing.engine import PostProcessingResult, ComfortField, ComfortStatistics
from src.postprocessing.comparison import compare_scenarios, DELTA_TOLERANCE


def _make_result(case_name: str, pet_value: float, ny: int = 10, nx: int = 10) -> PostProcessingResult:
    """Create a PostProcessingResult with uniform PET field at a known value."""
    data = np.full((ny, nx), pet_value, dtype=np.float32)
    fields = {
        "bio_pet*": [
            ComfortField(variable="bio_pet*", units="degree_C", time_s=0.0, data=data.copy()),
            ComfortField(variable="bio_pet*", units="degree_C", time_s=1800.0, data=data.copy()),
        ],
    }
    valid = data.flatten()
    stats = {
        "bio_pet*": ComfortStatistics(
            variable="bio_pet*", mean=pet_value, median=pet_value,
            std=0.0, p05=pet_value, p95=pet_value,
            min_val=pet_value, max_val=pet_value, n_valid=int(ny * nx),
        ),
    }
    return PostProcessingResult(case_name=case_name, fields=fields, statistics=stats)


class TestComparisonDeltas:
    """Hand-computed delta verification."""

    def test_uniform_cooling(self):
        """Baseline 35C, intervention 33C -> mean delta = -2.0."""
        baseline = _make_result("base", 35.0)
        intervention = _make_result("cool", 33.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        ds = result.delta_statistics["bio_pet*"]
        assert abs(ds.mean_delta - (-2.0)) < 0.01
        assert abs(ds.median_delta - (-2.0)) < 0.01
        assert ds.pct_improved == 1.0  # all cells improved
        assert ds.pct_worsened == 0.0

    def test_uniform_warming(self):
        """Baseline 30C, intervention 32C -> mean delta = +2.0, all worsened."""
        baseline = _make_result("base", 30.0)
        intervention = _make_result("warm", 32.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        ds = result.delta_statistics["bio_pet*"]
        assert abs(ds.mean_delta - 2.0) < 0.01
        assert ds.pct_worsened == 1.0
        assert ds.pct_improved == 0.0

    def test_no_change(self):
        """Same values -> delta = 0, all unchanged."""
        baseline = _make_result("base", 30.0)
        intervention = _make_result("same", 30.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        ds = result.delta_statistics["bio_pet*"]
        assert abs(ds.mean_delta) < 0.01
        assert ds.pct_unchanged == 1.0

    def test_threshold_crossing(self):
        """Baseline 36C (strong heat stress), intervention 34C (moderate).
        Should show cells crossing the 35C threshold."""
        baseline = _make_result("base", 36.0)
        intervention = _make_result("cool", 34.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        # Find the "Strong heat stress" threshold impact (35C)
        strong = [t for t in result.threshold_impacts if t.threshold_value == 35.0]
        assert len(strong) == 1
        ti = strong[0]
        assert ti.cells_above_baseline == 100  # all 10x10 cells above 35
        assert ti.cells_above_intervention == 0  # all below 35 after cooling
        assert ti.cells_improved == 100

    def test_max_improvement_value(self):
        """With uniform fields, max improvement == mean delta."""
        baseline = _make_result("base", 40.0)
        intervention = _make_result("cool", 35.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        ds = result.delta_statistics["bio_pet*"]
        assert abs(ds.max_improvement - (-5.0)) < 0.01

    def test_ranked_improvements_present(self):
        """Even with uniform fields, ranked improvements should be returned."""
        baseline = _make_result("base", 38.0)
        intervention = _make_result("cool", 35.0)
        result = compare_scenarios(baseline, intervention, resolution_m=10.0)

        assert len(result.ranked_improvements) > 0
        for ri in result.ranked_improvements:
            assert abs(ri.mean_delta - (-3.0)) < 0.01
