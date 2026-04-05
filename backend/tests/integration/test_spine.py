"""
Integration tests: full spine end-to-end.

Verifies Phase 1 exit criteria:
- Submit baseline scenario -> receive comfort maps + statistics + PDF report
- Submit baseline + intervention -> receive comparison report with difference maps
- Validation catches invalid scenarios
- Translation outputs are deterministic
- Confidence statements reflect data tier
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.spine import run_single_scenario, run_comparison
from src.execution.runner import RunStatus
from src.confidence.engine import ConfidenceLevel
from tests.fixtures.scenarios import (
    make_valid_baseline, make_valid_intervention, make_comparison_request,
)


class TestSingleScenarioSpine:
    """Exit criterion: Submit baseline scenario -> comfort maps + stats + report."""

    def test_full_spine_completes(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)

            assert result.error is None
            assert result.validation.valid
            assert result.translation is not None
            assert result.run_result is not None
            assert result.run_result.status == RunStatus.STUBBED
            assert result.postprocessing is not None
            assert result.confidence is not None
            assert result.report_path is not None

    def test_postprocessing_has_statistics(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)

            pp = result.postprocessing
            assert "bio_pet*" in pp.statistics
            assert pp.statistics["bio_pet*"].n_valid > 0
            assert pp.statistics["bio_pet*"].mean > 0

    def test_pet_classification_present(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)

            assert result.postprocessing.pet_classification is not None
            pc = result.postprocessing.pet_classification
            assert len(pc.class_fractions) > 0
            assert abs(sum(pc.class_fractions.values()) - 1.0) < 0.01

    def test_report_file_exists(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)

            assert result.report_path.exists()
            content = result.report_path.read_text(encoding="utf-8") if \
                result.report_path.suffix == ".html" else ""
            if content:
                assert "Executive Summary" in content
                assert "Methodology" in content
                assert "Confidence" in content

    def test_confidence_reflects_screening_tier(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)

            assert result.confidence.level == ConfidenceLevel.INDICATIVE
            assert len(result.confidence.caveats) > 0

    def test_invalid_scenario_blocked(self):
        """Validation errors prevent execution."""
        from src.models.scenario import Scenario, DomainConfig, BoundingBox
        scenario = Scenario(
            name="Invalid",
            domain=DomainConfig(
                bbox=BoundingBox(west=0, south=0, east=10, north=10),
                resolution_m=10.0,  # 1x1 cell -> too small
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_single_scenario(scenario, Path(tmpdir), stub=True)
            assert result.error is not None
            assert not result.validation.valid


class TestComparisonSpine:
    """Exit criterion: Submit baseline + intervention -> comparison report."""

    def test_comparison_completes(self):
        request = make_comparison_request()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(request, Path(tmpdir), stub=True)

            assert result.error is None
            assert result.comparison is not None
            assert result.report_path is not None

    def test_comparison_has_delta_statistics(self):
        request = make_comparison_request()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(request, Path(tmpdir), stub=True)

            assert "bio_pet*" in result.comparison.delta_statistics
            ds = result.comparison.delta_statistics["bio_pet*"]
            assert ds.n_valid > 0

    def test_comparison_has_threshold_impacts(self):
        request = make_comparison_request()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(request, Path(tmpdir), stub=True)

            assert len(result.comparison.threshold_impacts) > 0

    def test_comparison_has_ranked_improvements(self):
        request = make_comparison_request()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(request, Path(tmpdir), stub=True)

            assert len(result.comparison.ranked_improvements) > 0

    def test_comparison_report_contains_delta_sections(self):
        request = make_comparison_request()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_comparison(request, Path(tmpdir), stub=True)

            if result.report_path.suffix == ".html":
                content = result.report_path.read_text(encoding="utf-8")
                assert "Comparison" in content
                assert "Delta" in content or "delta" in content
                assert "Threshold" in content


class TestDeterminism:
    """Exit criterion: Same input -> identical output."""

    def test_translation_deterministic(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.translation.engine import translate_scenario
            r1 = translate_scenario(scenario, Path(tmpdir) / "run1")
            r2 = translate_scenario(scenario, Path(tmpdir) / "run2")

            # Namelist text must be identical
            t1 = r1["namelist"].read_text(encoding="utf-8")
            t2 = r2["namelist"].read_text(encoding="utf-8")
            assert t1 == t2

    def test_fingerprint_deterministic(self):
        s1 = make_valid_baseline()
        s2 = make_valid_baseline()
        assert s1.fingerprint() == s2.fingerprint()

    def test_full_spine_deterministic(self):
        """Same scenario through full spine twice -> identical statistics."""
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            r1 = run_single_scenario(scenario, Path(tmpdir) / "run1", stub=True)
            r2 = run_single_scenario(scenario, Path(tmpdir) / "run2", stub=True)

            assert r1.error is None and r2.error is None

            # Post-processing statistics must be identical
            for var_name in r1.postprocessing.statistics:
                s1 = r1.postprocessing.statistics[var_name]
                s2 = r2.postprocessing.statistics[var_name]
                assert s1.mean == s2.mean, f"{var_name} mean differs: {s1.mean} vs {s2.mean}"
                assert s1.median == s2.median, f"{var_name} median differs"
                assert s1.std == s2.std, f"{var_name} std differs"
                assert s1.p05 == s2.p05, f"{var_name} p05 differs"
                assert s1.p95 == s2.p95, f"{var_name} p95 differs"

            # PET classification fractions must be identical
            pc1 = r1.postprocessing.pet_classification
            pc2 = r2.postprocessing.pet_classification
            assert pc1.class_fractions == pc2.class_fractions
            assert pc1.dominant_class == pc2.dominant_class

            # Report HTML content must be identical (minus timestamp)
            if r1.report_path.suffix == ".html" and r2.report_path.suffix == ".html":
                h1 = r1.report_path.read_text(encoding="utf-8")
                h2 = r2.report_path.read_text(encoding="utf-8")
                # Strip the timestamp line for comparison
                import re
                h1_clean = re.sub(r'Generated: .*?<br>', '', h1)
                h2_clean = re.sub(r'Generated: .*?<br>', '', h2)
                assert h1_clean == h2_clean
