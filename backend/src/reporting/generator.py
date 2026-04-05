"""
Report generator: scenario/comparison results -> PDF.

Uses WeasyPrint to render HTML templates to PDF. Phase 1 uses inline
HTML templates; Phase 2 moves to Jinja2 file-based templates.

The 11 required report sections:
  1. Cover page (project name, date, data quality badge)
  2. Executive summary (key findings in plain language)
  3. Study area description (domain, data sources, quality tier)
  4. Methodology (PALM version, grid config, bio-met height, forcing)
  5. Baseline results (comfort maps, statistics, classification)
  6. Intervention description (what was changed and why)
  7. Intervention results (comfort maps, statistics, classification)
  8. Comparison (delta maps, threshold impact, ranked improvements)
  9. Confidence statement (data quality, caveats, suitability)
  10. Limitations and recommendations
  11. Technical appendix (model parameters, catalogue versions, fingerprints)
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from ..config import SCHEMA_VERSION, PALM_VERSION, BIOMET_TARGET_HEIGHT_M
from ..models.scenario import Scenario, ComparisonRequest, DataQualityTier
from ..postprocessing.engine import PostProcessingResult
from ..postprocessing.comparison import ComparisonResult
from ..confidence.engine import ConfidenceStatement, format_confidence_paragraph


def generate_report(
    scenario: Scenario,
    result: PostProcessingResult,
    confidence: ConfidenceStatement,
    output_path: Path,
    comparison: Optional[ComparisonResult] = None,
    intervention_scenario: Optional[Scenario] = None,
    intervention_result: Optional[PostProcessingResult] = None,
) -> Path:
    """
    Generate a PDF report from scenario results.

    Args:
        scenario: baseline scenario
        result: baseline post-processing results
        confidence: confidence assessment
        output_path: where to write the PDF
        comparison: optional comparison results (if intervention provided)
        intervention_scenario: optional intervention scenario
        intervention_result: optional intervention post-processing results

    Returns:
        Path to the generated PDF.
    """
    html = _build_html(
        scenario=scenario,
        result=result,
        confidence=confidence,
        comparison=comparison,
        intervention_scenario=intervention_scenario,
        intervention_result=intervention_result,
    )

    # Write HTML first (useful for debugging)
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    # Try WeasyPrint; fall back to HTML-only if not available
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(output_path))
    except ImportError:
        # WeasyPrint not installed — write HTML report only
        output_path = html_path

    return output_path


def _build_html(
    scenario: Scenario,
    result: PostProcessingResult,
    confidence: ConfidenceStatement,
    comparison: Optional[ComparisonResult] = None,
    intervention_scenario: Optional[Scenario] = None,
    intervention_result: Optional[PostProcessingResult] = None,
) -> str:
    """Build the complete HTML report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    is_comparison = comparison is not None

    sections = [
        _section_cover(scenario, confidence, now),
        _section_executive_summary(scenario, result, confidence, comparison),
        _section_study_area(scenario),
        _section_methodology(scenario),
        _section_baseline_results(result),
    ]

    if is_comparison and intervention_scenario:
        sections.append(_section_intervention_description(intervention_scenario))
        if intervention_result:
            sections.append(_section_intervention_results(intervention_result))
        sections.append(_section_comparison(comparison))
    else:
        # Single-scenario: sections 6-8 collapsed
        sections.append(_section_single_scenario_note())

    sections.extend([
        _section_confidence(confidence),
        _section_limitations(scenario, confidence),
        _section_appendix(scenario, result),
    ])

    body = "\n".join(sections)
    return _wrap_html(scenario.name, body, confidence)


def _wrap_html(title: str, body: str, confidence: ConfidenceStatement) -> str:
    watermark = ""
    if confidence.tier == DataQualityTier.SCREENING:
        watermark = """
        .watermark {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%) rotate(-45deg);
            font-size: 120px; color: rgba(200, 0, 0, 0.06);
            font-weight: bold; z-index: -1; pointer-events: none;
        }
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} - PALM4Umadeeasy Report</title>
<style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt;
           line-height: 1.5; color: #1a1a1a; }}
    h1 {{ font-size: 22pt; color: #2c3e50; border-bottom: 3px solid #2c3e50;
          padding-bottom: 8px; page-break-before: always; }}
    h1:first-of-type {{ page-break-before: avoid; }}
    h2 {{ font-size: 16pt; color: #34495e; margin-top: 1.5em; }}
    h3 {{ font-size: 13pt; color: #4a6785; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #bdc3c7; padding: 6px 10px; text-align: left; }}
    th {{ background-color: #ecf0f1; font-weight: 600; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 4px;
              font-size: 10pt; font-weight: 600; color: white; }}
    .badge-screening {{ background-color: #e74c3c; }}
    .badge-project {{ background-color: #f39c12; }}
    .badge-research {{ background-color: #27ae60; }}
    .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
                  margin: 1em 0; }}
    .stat-card {{ border: 1px solid #ddd; border-radius: 6px; padding: 12px;
                  text-align: center; }}
    .stat-value {{ font-size: 20pt; font-weight: 700; color: #2c3e50; }}
    .stat-label {{ font-size: 9pt; color: #7f8c8d; }}
    .caveat {{ background: #fef9e7; border-left: 4px solid #f39c12;
               padding: 10px 14px; margin: 1em 0; font-size: 10pt; }}
    .delta-positive {{ color: #e74c3c; }}
    .delta-negative {{ color: #27ae60; }}
    {watermark}
</style>
</head>
<body>
{"<div class='watermark'>SCREENING</div>" if confidence.tier == DataQualityTier.SCREENING else ""}
{body}
</body>
</html>"""


# --- Section builders ---

def _section_cover(scenario: Scenario, confidence: ConfidenceStatement, date: str) -> str:
    tier = scenario.effective_data_tier
    badge_class = f"badge-{tier.value}"
    return f"""
<div style="text-align: center; padding: 60px 0 40px 0;">
    <h1 style="font-size: 28pt; border: none; page-break-before: avoid;">
        Microclimate Assessment Report
    </h1>
    <h2 style="color: #7f8c8d; font-weight: 400;">{scenario.name}</h2>
    <p><span class="badge {badge_class}">{tier.value.upper()}</span></p>
    <p style="color: #95a5a6; margin-top: 40px;">
        Generated: {date}<br>
        PALM4Umadeeasy v{SCHEMA_VERSION} | PALM {PALM_VERSION}
    </p>
</div>
"""


def _section_executive_summary(
    scenario: Scenario, result: PostProcessingResult,
    confidence: ConfidenceStatement,
    comparison: Optional[ComparisonResult],
) -> str:
    pet_stats = result.statistics.get("bio_pet*")
    pet_class = result.pet_classification

    summary_lines = []
    if pet_stats:
        summary_lines.append(
            f"Mean PET across the study area: <strong>{pet_stats.mean:.1f} °C</strong> "
            f"(range: {pet_stats.min_val:.1f} – {pet_stats.max_val:.1f} °C)."
        )
    if pet_class:
        summary_lines.append(
            f"Dominant thermal perception: <strong>{pet_class.dominant_class}</strong> "
            f"({pet_class.stress_level})."
        )
    if comparison:
        pet_delta = comparison.delta_statistics.get("bio_pet*")
        if pet_delta:
            direction = "cooling" if pet_delta.mean_delta < 0 else "warming"
            summary_lines.append(
                f"The intervention produces a mean {direction} of "
                f"<strong>{abs(pet_delta.mean_delta):.1f} °C PET</strong>, "
                f"improving {pet_delta.pct_improved * 100:.0f}% of the domain."
            )

    summary_lines.append(f"<em>{confidence.headline}.</em>")

    return f"""
<h1>1. Executive Summary</h1>
<p>{"</p><p>".join(summary_lines)}</p>
"""


def _section_study_area(scenario: Scenario) -> str:
    d = scenario.domain
    bbox = d.bbox
    ds = scenario.data_sources
    return f"""
<h1>2. Study Area</h1>
<table>
    <tr><th>Parameter</th><th>Value</th></tr>
    <tr><td>Bounding box (W, S, E, N)</td>
        <td>{bbox.west:.2f}, {bbox.south:.2f}, {bbox.east:.2f}, {bbox.north:.2f}</td></tr>
    <tr><td>EPSG</td><td>{d.epsg}</td></tr>
    <tr><td>Grid resolution</td><td>{d.resolution_m} m</td></tr>
    <tr><td>Domain size</td><td>{d.nx} x {d.ny} cells ({d.nx * d.resolution_m:.0f} x {d.ny * d.resolution_m:.0f} m)</td></tr>
    <tr><td>Vertical levels</td><td>{d.nz} (dz = {d.dz} m, domain height = {d.nz * d.dz:.0f} m)</td></tr>
    <tr><td>Building data</td><td>{ds.buildings.source_type} ({ds.buildings.quality_tier.value})</td></tr>
    <tr><td>Terrain data</td><td>{ds.terrain.source_type} ({ds.terrain.quality_tier.value})</td></tr>
    <tr><td>Vegetation data</td><td>{ds.vegetation.source_type} ({ds.vegetation.quality_tier.value})</td></tr>
    <tr><td>Effective data tier</td><td><strong>{scenario.effective_data_tier.value.upper()}</strong></td></tr>
</table>
"""


def _section_methodology(scenario: Scenario) -> str:
    sim = scenario.simulation
    dz = scenario.domain.dz
    actual_h = int(1.099 / dz) * dz
    return f"""
<h1>3. Methodology</h1>
<h2>3.1 Simulation Model</h2>
<p>PALM model system version {PALM_VERSION} (Maronga et al., 2020).
Large-eddy simulation with embedded bio-meteorological module.</p>

<h2>3.2 Grid Configuration</h2>
<table>
    <tr><th>Parameter</th><th>Value</th></tr>
    <tr><td>Horizontal resolution (dx = dy)</td><td>{scenario.domain.resolution_m} m</td></tr>
    <tr><td>Vertical resolution (dz)</td><td>{dz} m</td></tr>
    <tr><td>Vertical levels (nz)</td><td>{scenario.domain.nz}</td></tr>
    <tr><td>Bio-met output height (VDI 3787)</td><td>{actual_h:.1f} m (target: {BIOMET_TARGET_HEIGHT_M} m)</td></tr>
</table>

<h2>3.3 Meteorological Forcing</h2>
<p>Archetype: <strong>{sim.forcing.value.replace('_', ' ').title()}</strong>.
Synthetic profile representative of NRW (Region 5) conditions.
<em>Note: Phase 1 archetype values are plausible estimates, not traced to a specific
DWD TRY dataset. Production use requires validated forcing from DWD Open Data or
site measurements.</em></p>
<p>Simulation duration: {sim.simulation_hours} hours.
Output interval: {sim.output_interval_s:.0f} s.</p>

<h2>3.4 Thermal Comfort Indices</h2>
<p>PET computed following Hoeppe (1999) with Walther &amp; Goestchel (2018) corrections
via pythermalcomfort. Classification per VDI 3787 Blatt 2 (9 classes).</p>
<p>UTCI computed following Broede et al. (2012).</p>

<h2>3.5 Height Convention</h2>
<p>Bio-meteorological variables are output at {actual_h:.1f} m above ground level,
corresponding to the nearest grid level below {BIOMET_TARGET_HEIGHT_M} m
(VDI 3787: diagnostic height 1.1 m, hardcoded in PALM source as
<code>INT(1.099/dz)*dz</code>). See ADR-003 for details.</p>
"""


def _section_baseline_results(result: PostProcessingResult) -> str:
    rows = []
    for var_name, stats in result.statistics.items():
        rows.append(f"""
        <tr>
            <td>{var_name}</td>
            <td>{stats.mean:.1f}</td>
            <td>{stats.median:.1f}</td>
            <td>{stats.std:.1f}</td>
            <td>{stats.p05:.1f}</td>
            <td>{stats.p95:.1f}</td>
            <td>{stats.min_val:.1f}</td>
            <td>{stats.max_val:.1f}</td>
        </tr>""")

    pet_class_html = ""
    if result.pet_classification:
        pc = result.pet_classification
        class_rows = "".join(
            f"<tr><td>{k}</td><td>{v * 100:.1f}%</td></tr>"
            for k, v in sorted(pc.class_fractions.items(), key=lambda x: -x[1])
        )
        pet_class_html = f"""
<h2>4.2 PET Classification (VDI 3787)</h2>
<table>
    <tr><th>Thermal Perception</th><th>Domain Fraction</th></tr>
    {class_rows}
</table>
<p>Dominant class: <strong>{pc.dominant_class}</strong> ({pc.stress_level})</p>
"""

    return f"""
<h1>4. Baseline Results</h1>
<h2>4.1 Summary Statistics (time-averaged)</h2>
<table>
    <tr><th>Variable</th><th>Mean</th><th>Median</th><th>Std</th>
        <th>P05</th><th>P95</th><th>Min</th><th>Max</th></tr>
    {"".join(rows)}
</table>
{pet_class_html}
<p><em>Maps: see attached GeoTIFF files or interactive viewer.</em></p>
"""


def _section_intervention_description(intervention: Scenario) -> str:
    lines = []
    if intervention.trees:
        lines.append(f"{len(intervention.trees)} tree(s) placed")
    if intervention.surface_changes:
        lines.append(f"{len(intervention.surface_changes)} surface change(s)")
    if intervention.green_roofs:
        lines.append(
            f"{len(intervention.green_roofs)} green roof(s) "
            f"<strong style='color:#e74c3c;'>(NOT YET SIMULATED — ignored in PALM input)</strong>"
        )

    desc = intervention.description or "No description provided."
    items = "<li>" + "</li><li>".join(lines) + "</li>" if lines else "<li>No interventions</li>"

    return f"""
<h1>5. Intervention Description</h1>
<p>{desc}</p>
<h2>Intervention Elements</h2>
<ul>{items}</ul>
"""


def _section_intervention_results(result: PostProcessingResult) -> str:
    rows = []
    for var_name, stats in result.statistics.items():
        rows.append(f"""
        <tr>
            <td>{var_name}</td>
            <td>{stats.mean:.1f}</td>
            <td>{stats.median:.1f}</td>
            <td>{stats.p05:.1f} – {stats.p95:.1f}</td>
        </tr>""")

    return f"""
<h1>6. Intervention Results</h1>
<table>
    <tr><th>Variable</th><th>Mean</th><th>Median</th><th>P05–P95 Range</th></tr>
    {"".join(rows)}
</table>
"""


def _section_comparison(comparison: Optional[ComparisonResult]) -> str:
    if comparison is None:
        return ""

    # Delta statistics table
    delta_rows = []
    for var_name, ds in comparison.delta_statistics.items():
        color = "delta-negative" if ds.mean_delta < 0 else "delta-positive"
        delta_rows.append(f"""
        <tr>
            <td>{var_name}</td>
            <td class="{color}">{ds.mean_delta:+.2f}</td>
            <td>{ds.median_delta:+.2f}</td>
            <td>{ds.max_improvement:+.2f}</td>
            <td>{ds.pct_improved * 100:.0f}%</td>
            <td>{ds.pct_worsened * 100:.0f}%</td>
        </tr>""")

    # Threshold impact table
    thresh_rows = []
    for ti in comparison.threshold_impacts:
        thresh_rows.append(f"""
        <tr>
            <td>{ti.threshold_name}</td>
            <td>{ti.threshold_value:.0f} °C</td>
            <td>{ti.cells_above_baseline}</td>
            <td>{ti.cells_above_intervention}</td>
            <td>{ti.cells_improved}</td>
            <td>{ti.pct_improved * 100:.1f}%</td>
        </tr>""")

    # Ranked improvements
    rank_rows = []
    for ri in comparison.ranked_improvements[:5]:
        rank_rows.append(f"""
        <tr>
            <td>{ri.variable}</td>
            <td>{ri.region_description}</td>
            <td>{ri.mean_delta:+.2f}</td>
            <td>{ri.area_m2:.0f}</td>
        </tr>""")

    return f"""
<h1>7. Comparison: Baseline vs. Intervention</h1>
<p>Convention: delta = intervention - baseline. Negative values indicate cooling (improvement).</p>

<h2>7.1 Delta Statistics</h2>
<table>
    <tr><th>Variable</th><th>Mean Δ</th><th>Median Δ</th><th>Max Improvement</th>
        <th>% Improved</th><th>% Worsened</th></tr>
    {"".join(delta_rows)}
</table>

<h2>7.2 Threshold Impact (PET)</h2>
<table>
    <tr><th>Threshold</th><th>Value</th><th>Cells Above (Baseline)</th>
        <th>Cells Above (Intervention)</th><th>Cells Improved</th><th>% of Domain</th></tr>
    {"".join(thresh_rows)}
</table>

<h2>7.3 Ranked Improvement Regions</h2>
<table>
    <tr><th>Variable</th><th>Region</th><th>Mean Δ</th><th>Area (m²)</th></tr>
    {"".join(rank_rows)}
</table>
"""


def _section_single_scenario_note() -> str:
    return """
<h1>5–7. Comparison</h1>
<p>This report covers a single scenario (no intervention comparison).
To generate a comparison report, submit both a baseline and an intervention scenario.</p>
"""


def _section_confidence(confidence: ConfidenceStatement) -> str:
    paragraph = format_confidence_paragraph(confidence)
    # Convert markdown-like bold to HTML (pair-wise replacement)
    import re
    html_para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', paragraph)
    html_para = html_para.replace("\n- ", "\n<li>")
    html_para = html_para.replace("\n\n", "</p><p>").replace("\n", "<br>")

    return f"""
<h1>8. Data Quality and Confidence</h1>
<div class="caveat">
{html_para}
</div>
"""


def _section_limitations(scenario: Scenario, confidence: ConfidenceStatement) -> str:
    limitations = [
        "PALM assumes horizontally homogeneous meteorological forcing. "
        "Local forcing variations (e.g. lake breezes) are not captured.",
        "Building interiors are not modelled. Indoor-outdoor thermal exchanges "
        "are simplified.",
        "Vegetation is represented via leaf area density (LAD) profiles. "
        "Species-specific transpiration is parameterised, not mechanistic.",
        "Bio-met comfort indices assume a standardised human (35 years, 75 kg). "
        "Individual physiological variation is not captured.",
        f"Grid resolution ({scenario.domain.resolution_m}m) limits the "
        f"representation of sub-grid features (narrow streets, small gardens).",
    ]

    if confidence.tier == DataQualityTier.SCREENING:
        limitations.append(
            "Screening-level building data may underestimate or overestimate "
            "building heights, affecting shadow patterns and wind channelling."
        )

    items = "".join(f"<li>{lim}</li>" for lim in limitations)

    return f"""
<h1>9. Limitations and Recommendations</h1>
<h2>9.1 Model Limitations</h2>
<ul>{items}</ul>

<h2>9.2 Recommendations</h2>
<ul>
    <li>For regulatory submissions, upgrade to project-tier data (surveyed building geometry, measured trees).</li>
    <li>Validate results against field measurements where possible.</li>
    <li>Consider multiple forcing scenarios to assess sensitivity.</li>
    <li>For detailed pedestrian wind comfort, use wind-specific output at higher spatial resolution.</li>
</ul>
"""


def _section_appendix(scenario: Scenario, result: PostProcessingResult) -> str:
    return f"""
<h1>10. Technical Appendix</h1>
<table>
    <tr><th>Parameter</th><th>Value</th></tr>
    <tr><td>Schema version</td><td>{scenario.schema_version}</td></tr>
    <tr><td>PALM version</td><td>{PALM_VERSION}</td></tr>
    <tr><td>Scenario fingerprint</td><td><code>{scenario.fingerprint()}</code></td></tr>
    <tr><td>Bio-met target height</td><td>{BIOMET_TARGET_HEIGHT_M} m (VDI 3787)</td></tr>
    <tr><td>Forcing archetype</td><td>{scenario.simulation.forcing.value}</td></tr>
    <tr><td>Trees placed</td><td>{len(scenario.trees)}</td></tr>
    <tr><td>Surface changes</td><td>{len(scenario.surface_changes)}</td></tr>
    <tr><td>Green roofs</td><td>{len(scenario.green_roofs)}{' (not yet simulated)' if scenario.green_roofs else ''}</td></tr>
    <tr><td>Output timesteps</td><td>{result.metadata.get('n_timesteps', 'N/A')}</td></tr>
    <tr><td>Generated by</td><td>PALM4Umadeeasy v{SCHEMA_VERSION}</td></tr>
</table>

<h2>10.1 References</h2>
<ul>
    <li>Maronga, B., et al. (2020). Overview of the PALM model system 6.0. <em>Geosci. Model Dev.</em>, 13, 1335-1372.</li>
    <li>Hoeppe, P. (1999). The physiological equivalent temperature. <em>Int. J. Biometeorol.</em>, 43, 71-75.</li>
    <li>Walther, E., Goestchel, Q. (2018). The P.E.T. comfort index. <em>Indoor Air</em>, 28, 315-324.</li>
    <li>Broede, P., et al. (2012). Deriving the operational procedure for the UTCI. <em>Int. J. Biometeorol.</em>, 56, 481-494.</li>
    <li>VDI 3787 Blatt 2 (2008). Environmental meteorology — Methods for the human-biometeorological assessment of climate.</li>
</ul>
"""
