"""
Confidence propagation engine.

Tracks data quality tiers through the pipeline and generates
appropriate confidence statements for results and reports.

Principle: the weakest input determines the overall confidence.
A screening-tier building dataset makes the entire run screening-tier,
regardless of how good the vegetation data is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..models.scenario import DataQualityTier, Scenario


class ConfidenceLevel(str, Enum):
    """Output confidence levels mapped from data quality tiers."""
    INDICATIVE = "indicative"       # screening tier
    QUANTITATIVE = "quantitative"   # project tier
    REFERENCE = "reference"         # research tier


@dataclass
class ConfidenceStatement:
    """Structured confidence information for a result."""
    level: ConfidenceLevel
    tier: DataQualityTier
    headline: str
    detail: str
    caveats: list[str]
    suitable_for: list[str]
    not_suitable_for: list[str]


# Mapping from data quality tier to confidence messaging
CONFIDENCE_MAP = {
    DataQualityTier.SCREENING: {
        "level": ConfidenceLevel.INDICATIVE,
        "headline": "Indicative results - screening quality",
        "detail": (
            "These results are based on screening-level input data "
            "(e.g. OSM building footprints, estimated heights, default vegetation). "
            "They indicate trends and relative differences but should not be cited "
            "as absolute values."
        ),
        "suitable_for": [
            "Early-stage feasibility assessment",
            "Comparing relative effectiveness of interventions",
            "Internal concept discussions",
            "Identifying areas for detailed investigation",
        ],
        "not_suitable_for": [
            "Regulatory submissions (Bebauungsplan climate assessment)",
            "Quantitative claims in public reports",
            "Design certification",
            "Legal proceedings",
        ],
    },
    DataQualityTier.PROJECT: {
        "level": ConfidenceLevel.QUANTITATIVE,
        "headline": "Quantitative results - project quality",
        "detail": (
            "These results are based on project-level input data "
            "(e.g. surveyed building geometry, measured tree dimensions, "
            "site-specific surface materials). Absolute values can be cited "
            "with appropriate uncertainty margins."
        ),
        "suitable_for": [
            "Bebauungsplan climate assessments",
            "Quantitative reporting with stated uncertainty",
            "Design optimization",
            "Stakeholder presentations with numerical claims",
            "Comparison across design alternatives",
        ],
        "not_suitable_for": [
            "Peer-reviewed scientific publication (without additional validation)",
            "Absolute claims without uncertainty bounds",
        ],
    },
    DataQualityTier.RESEARCH: {
        "level": ConfidenceLevel.REFERENCE,
        "headline": "Reference results - research quality",
        "detail": (
            "These results are based on research-grade input data "
            "(e.g. LiDAR-derived building models, measured LAD profiles, "
            "on-site meteorological forcing). Results are suitable for "
            "scientific citation with full methodology documentation."
        ),
        "suitable_for": [
            "Scientific publication",
            "Regulatory submissions at highest confidence",
            "Benchmark studies",
            "Validation against field measurements",
            "Expert testimony",
        ],
        "not_suitable_for": [
            "Claims beyond the validated domain/period",
        ],
    },
}


def assess_confidence(scenario: Scenario) -> ConfidenceStatement:
    """
    Determine the confidence level for a scenario based on its data sources.

    The effective tier is the weakest (lowest quality) data source.
    """
    tier = scenario.effective_data_tier
    conf = CONFIDENCE_MAP[tier]

    caveats = _build_caveats(scenario)

    return ConfidenceStatement(
        level=conf["level"],
        tier=tier,
        headline=conf["headline"],
        detail=conf["detail"],
        caveats=caveats,
        suitable_for=conf["suitable_for"],
        not_suitable_for=conf["not_suitable_for"],
    )


def format_confidence_paragraph(statement: ConfidenceStatement) -> str:
    """Format a confidence statement as a readable paragraph for reports."""
    lines = [
        f"**{statement.headline}**",
        "",
        statement.detail,
    ]

    if statement.caveats:
        lines.append("")
        lines.append("Caveats:")
        for caveat in statement.caveats:
            lines.append(f"- {caveat}")

    lines.append("")
    lines.append("Suitable for:")
    for item in statement.suitable_for:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("Not suitable for:")
    for item in statement.not_suitable_for:
        lines.append(f"- {item}")

    return "\n".join(lines)


def _build_caveats(scenario: Scenario) -> list[str]:
    """Generate scenario-specific caveats."""
    caveats = []
    ds = scenario.data_sources

    if ds.buildings.quality_tier == DataQualityTier.SCREENING:
        caveats.append(
            f"Building data ({ds.buildings.source_type}): heights and geometry "
            f"are estimated. Actual building configurations may differ."
        )

    if ds.terrain.quality_tier == DataQualityTier.SCREENING:
        caveats.append(
            f"Terrain data ({ds.terrain.source_type}): resolution may be insufficient "
            f"for small-scale elevation features."
        )

    # Stub runner caveat
    caveats.append(
        "PALM simulation was run in stub mode (synthetic output). "
        "Results demonstrate pipeline functionality but do not represent "
        "actual microclimate physics."
    )

    # Bio-met height caveat (ADR-003)
    dz = scenario.domain.dz
    actual_height = int(1.099 / dz) * dz
    if abs(actual_height - 1.1) > 0.5:
        caveats.append(
            f"Bio-met output height ({actual_height:.1f}m) deviates from "
            f"VDI 3787 target (1.1m) due to grid resolution dz={dz}m."
        )

    # Small domain caveat
    if scenario.domain.nx < 20 or scenario.domain.ny < 20:
        caveats.append(
            "Small domain size may produce boundary effects. "
            "Consider expanding the domain for production use."
        )

    return caveats
