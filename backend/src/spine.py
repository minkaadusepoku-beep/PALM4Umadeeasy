"""
Foundation Spine: end-to-end orchestrator.

JSON in -> validation -> translation -> execution -> post-processing
-> comparison (optional) -> confidence -> report -> output.

This is the single entry point for the headless pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models.scenario import Scenario, ComparisonRequest
from .validation.engine import validate_scenario, validate_comparison, ValidationResult
from .translation.engine import translate_scenario
from .execution.runner import run_palm, RunResult
from .postprocessing.engine import postprocess_run, PostProcessingResult, verify_pet
from .postprocessing.comparison import compare_scenarios, ComparisonResult
from .confidence.engine import assess_confidence, ConfidenceStatement
from .reporting.generator import generate_report

# PET verification pass/fail threshold.
# Stub mode: synthetic PET is not physics-based, so MAE will be large.
# Real PALM mode: MAE should be < 2K (pythermalcomfort vs PALM bio-met).
PET_VERIFICATION_THRESHOLD_K = 2.0


@dataclass
class SpineResult:
    """Complete output of the foundation spine."""
    scenario: Scenario
    validation: ValidationResult
    translation: Optional[dict] = None
    run_result: Optional[RunResult] = None
    postprocessing: Optional[PostProcessingResult] = None
    confidence: Optional[ConfidenceStatement] = None
    report_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class ComparisonSpineResult:
    """Complete output of a comparison run."""
    baseline: SpineResult
    intervention: SpineResult
    comparison_validation: ValidationResult
    comparison: Optional[ComparisonResult] = None
    confidence: Optional[ConfidenceStatement] = None  # weakest of baseline/intervention
    report_path: Optional[Path] = None
    error: Optional[str] = None


def run_single_scenario(
    scenario: Scenario,
    output_dir: Path,
    stub: bool = True,
) -> SpineResult:
    """
    Execute the full spine for a single scenario.

    Args:
        scenario: the scenario to process
        output_dir: root output directory
        stub: if True, use synthetic PALM output (Windows dev mode)
    """
    result = SpineResult(scenario=scenario, validation=ValidationResult(valid=True))

    # 1. Validate
    result.validation = validate_scenario(scenario)
    if not result.validation.valid:
        result.error = f"Validation failed with {len(result.validation.errors)} error(s)"
        return result

    # 2. Translate
    translation_dir = output_dir / "input"
    result.translation = translate_scenario(scenario, translation_dir)

    # 3. Execute
    palm_output_dir = output_dir / "output"
    # Derive deterministic seed from scenario fingerprint
    seed = int(scenario.fingerprint()[:8], 16)
    result.run_result = run_palm(
        case_name=result.translation["case_name"],
        input_files=result.translation,
        output_dir=palm_output_dir,
        stub=stub,
        seed=seed,
    )

    # 4. Post-process
    result.postprocessing = postprocess_run(
        case_name=result.translation["case_name"],
        output_files=result.run_result.output_files,
    )

    # 4b. PET verification (cross-validate PALM PET against pythermalcomfort)
    pp = result.postprocessing
    if "bio_pet*" in pp.fields and "bio_mrt*" in pp.fields:
        from .translation.dynamic_driver import ARCHETYPE_PROFILES
        profile = ARCHETYPE_PROFILES[scenario.simulation.forcing]
        # Use midday values (index 6 = hour 12 local) as representative met conditions
        midday_idx = min(6, len(profile["temperature_K"]) - 1)
        ta_C = profile["temperature_K"][midday_idx] - 273.15
        wind = profile["wind_u"][midday_idx]
        # Approximate RH from specific humidity and temperature
        qv = profile["qv"][midday_idx]
        p = profile["surface_pressure_Pa"]
        rh_pct = min(100.0, qv / (0.622 * 611.2 * 2.718 ** (17.67 * ta_C / (ta_C + 243.5)) / p) * 100)

        pp.pet_verification = verify_pet(
            palm_pet_fields=pp.fields["bio_pet*"],
            mrt_fields=pp.fields["bio_mrt*"],
            ta_C=ta_C,
            rh_pct=rh_pct,
            wind_ms=wind,
        )
        pp.metadata["pet_verification_passed"] = (
            pp.pet_verification.mean_absolute_error <= PET_VERIFICATION_THRESHOLD_K
            if pp.pet_verification.n_points > 0 else None
        )

    # 5. Confidence
    result.confidence = assess_confidence(scenario)

    # 6. Report
    report_path = output_dir / "report.pdf"
    result.report_path = generate_report(
        scenario=scenario,
        result=result.postprocessing,
        confidence=result.confidence,
        output_path=report_path,
    )

    return result


def run_comparison(
    request: ComparisonRequest,
    output_dir: Path,
    stub: bool = True,
) -> ComparisonSpineResult:
    """
    Execute the full spine for a baseline + intervention comparison.
    """
    # Validate comparison compatibility BEFORE running simulations
    comp_validation = validate_comparison(request)

    if not comp_validation.valid:
        # Return early — don't waste compute on incompatible scenarios
        empty_baseline = SpineResult(
            scenario=request.baseline,
            validation=ValidationResult(valid=True),
        )
        empty_intervention = SpineResult(
            scenario=request.intervention,
            validation=ValidationResult(valid=True),
        )
        return ComparisonSpineResult(
            baseline=empty_baseline,
            intervention=empty_intervention,
            comparison_validation=comp_validation,
            error=f"Comparison validation failed: {len(comp_validation.errors)} error(s)",
        )

    baseline_dir = output_dir / "baseline"
    intervention_dir = output_dir / "intervention"

    baseline_result = run_single_scenario(request.baseline, baseline_dir, stub=stub)
    intervention_result = run_single_scenario(request.intervention, intervention_dir, stub=stub)

    result = ComparisonSpineResult(
        baseline=baseline_result,
        intervention=intervention_result,
        comparison_validation=comp_validation,
    )

    if baseline_result.error or intervention_result.error:
        result.error = "One or both scenarios failed to complete"
        return result

    # Compare
    result.comparison = compare_scenarios(
        baseline=baseline_result.postprocessing,
        intervention=intervention_result.postprocessing,
        resolution_m=request.baseline.domain.resolution_m,
    )

    # Determine and store the weakest confidence of the two scenarios
    report_path = output_dir / "comparison_report.pdf"
    confidence = _weakest_confidence(baseline_result.confidence, intervention_result.confidence)
    result.confidence = confidence
    result.report_path = generate_report(
        scenario=request.baseline,
        result=baseline_result.postprocessing,
        confidence=confidence,
        output_path=report_path,
        comparison=result.comparison,
        intervention_scenario=request.intervention,
        intervention_result=intervention_result.postprocessing,
    )

    return result


# Data quality tier ranking (lower = weaker)
_TIER_RANK = {
    "screening": 0,
    "project": 1,
    "research": 2,
}


def _weakest_confidence(
    a: ConfidenceStatement, b: ConfidenceStatement,
) -> ConfidenceStatement:
    """Return the confidence statement with the weaker (lower) data quality tier."""
    rank_a = _TIER_RANK.get(a.tier.value, 0)
    rank_b = _TIER_RANK.get(b.tier.value, 0)
    return a if rank_a <= rank_b else b
