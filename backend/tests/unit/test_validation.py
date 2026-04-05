"""
Unit tests for the validation engine.

Tests 17+ invalid scenarios to verify that the validation engine
catches all expected issues.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation.engine import validate_scenario, validate_comparison, Severity
from tests.fixtures.scenarios import (
    make_valid_baseline, make_valid_intervention,
    make_comparison_request, INVALID_SCENARIOS,
)


class TestValidScenarios:
    def test_valid_baseline_passes(self):
        result = validate_scenario(make_valid_baseline())
        assert result.valid
        assert len(result.errors) == 0

    def test_valid_intervention_passes(self):
        result = validate_scenario(make_valid_intervention())
        assert result.valid
        assert len(result.errors) == 0


class TestInvalidScenarios:
    @pytest.mark.parametrize(
        "name,scenario_fn,expected_code",
        INVALID_SCENARIOS,
        ids=[s[0] for s in INVALID_SCENARIOS],
    )
    def test_invalid_scenario_caught(self, name, scenario_fn, expected_code):
        scenario = scenario_fn()
        result = validate_scenario(scenario)
        all_codes = [i.code for i in result.issues]
        matching = [c for c in all_codes if expected_code in c]
        assert len(matching) > 0, (
            f"Expected issue containing '{expected_code}' but got: {all_codes}"
        )


class TestComparisonValidation:
    def test_valid_comparison_passes(self):
        request = make_comparison_request()
        result = validate_comparison(request)
        assert result.valid

    def test_mismatched_domains_rejected(self):
        request = make_comparison_request()
        request.intervention.domain.bbox.east = 357000  # different domain
        result = validate_comparison(request)
        assert not result.valid
        codes = [i.code for i in result.issues]
        assert any("domain_mismatch" in c for c in codes)

    def test_mismatched_resolution_rejected(self):
        request = make_comparison_request()
        request.intervention.domain.resolution_m = 5.0
        result = validate_comparison(request)
        assert not result.valid
        codes = [i.code for i in result.issues]
        assert any("resolution_mismatch" in c for c in codes)

    def test_different_forcing_warns(self):
        request = make_comparison_request()
        request.intervention.simulation.forcing = ForcingArchetype.HEAT_WAVE_DAY
        result = validate_comparison(request)
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        codes = [w.code for w in warnings]
        assert any("forcing_mismatch" in c for c in codes)


from src.models.scenario import ForcingArchetype
