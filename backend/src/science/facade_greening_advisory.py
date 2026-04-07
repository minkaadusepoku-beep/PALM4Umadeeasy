"""Facade greening advisory estimator (NON-PALM, NON-COUPLED).

This module provides simple, transparent first-order estimates of the
benefits a vertical greening intervention is *likely* to provide on a
single facade. It is an advisory layer only.

CRITICAL: Outputs of this module MUST NEVER be merged, blended, averaged,
or co-displayed with PALM/PALM-4U simulation results without an explicit
provenance tag. Every dict returned by this module carries:

    "result_kind": "advisory_non_palm"
    "coupled_with_palm": False
    "method": <short identifier>
    "uncertainty": "high"

Downstream code (API responses, reports, frontend) is required to
preserve and display these flags. The mixing of advisory and PALM-coupled
outputs would constitute a scientific-honesty violation per the project
operating principles.

References (ranges chosen on the conservative end):
- Aduse-Poku, M. (2024). Methodology for quantification of pollutant
  absorption by climbing plants. ScienceDirect.
- Aduse-Poku, M. (2025). Quantifying pollutant absorption potential of
  facade climbing plants. Springer Urban Ecosystems.
- Pugh et al. (2012); Ottelé et al. (2010); Perini et al. (2011) for
  LAI ranges of Hedera helix, Parthenocissus and similar climbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResultKind = Literal["advisory_non_palm"]
SpeciesId = Literal["hedera_helix", "parthenocissus", "generic_climber"]

# Conservative literature ranges. LAI = leaf area index (m2 leaf / m2 facade).
SPECIES_LAI: dict[str, tuple[float, float, float]] = {
    # (low, central, high)
    "hedera_helix": (3.0, 5.5, 8.0),
    "parthenocissus": (2.5, 4.5, 6.5),
    "generic_climber": (2.0, 4.0, 6.0),
}

# Per-leaf-area annual deposition rates (g per m2 leaf per year).
# Conservative central estimates derived from published facade-greening
# absorption studies (PM10, PM2.5, NO2, O3). Treat as order-of-magnitude.
DEPOSITION_RATES_G_PER_M2_LEAF_YEAR: dict[str, float] = {
    "PM10": 1.8,
    "PM2_5": 0.6,
    "NO2": 0.4,
    "O3": 0.5,
}

# Cooling effect: facade-side air-temperature reduction during summer
# afternoons (degC). Range, not single number.
COOLING_DELTA_T_RANGE_C: tuple[float, float] = (0.5, 2.5)

# Building-energy advisory: typical reported summer cooling-load
# reduction for shaded south/west facades (fraction).
ENERGY_COOLING_REDUCTION_RANGE: tuple[float, float] = (0.05, 0.20)


@dataclass(frozen=True)
class FacadeGreeningInput:
    facade_area_m2: float
    species: SpeciesId
    coverage_fraction: float = 1.0  # 0..1, fraction of facade actually greened
    climate_zone: str = "temperate"


def _provenance() -> dict:
    return {
        "result_kind": "advisory_non_palm",
        "coupled_with_palm": False,
        "method": "literature_first_order_estimate",
        "uncertainty": "high",
        "warning": (
            "Advisory estimate only. NOT a PALM/PALM-4U simulation result. "
            "Do not combine with PALM outputs without preserving this flag."
        ),
    }


def estimate_pollutant_uptake(inp: FacadeGreeningInput) -> dict:
    """Annual pollutant uptake (kg/year), low/central/high bands."""
    if inp.facade_area_m2 <= 0:
        raise ValueError("facade_area_m2 must be > 0")
    if not 0.0 <= inp.coverage_fraction <= 1.0:
        raise ValueError("coverage_fraction must be in [0, 1]")
    if inp.species not in SPECIES_LAI:
        raise ValueError(f"unknown species: {inp.species}")

    lai_low, lai_mid, lai_high = SPECIES_LAI[inp.species]
    leaf_area_low = inp.facade_area_m2 * inp.coverage_fraction * lai_low
    leaf_area_mid = inp.facade_area_m2 * inp.coverage_fraction * lai_mid
    leaf_area_high = inp.facade_area_m2 * inp.coverage_fraction * lai_high

    pollutants: dict[str, dict[str, float]] = {}
    for poll, rate in DEPOSITION_RATES_G_PER_M2_LEAF_YEAR.items():
        pollutants[poll] = {
            "low_kg_per_year": round(leaf_area_low * rate / 1000.0, 4),
            "central_kg_per_year": round(leaf_area_mid * rate / 1000.0, 4),
            "high_kg_per_year": round(leaf_area_high * rate / 1000.0, 4),
        }

    return {
        **_provenance(),
        "inputs": {
            "facade_area_m2": inp.facade_area_m2,
            "species": inp.species,
            "coverage_fraction": inp.coverage_fraction,
        },
        "leaf_area_m2": {
            "low": round(leaf_area_low, 1),
            "central": round(leaf_area_mid, 1),
            "high": round(leaf_area_high, 1),
        },
        "pollutants": pollutants,
        "notes": (
            "Linear deposition model; ignores saturation, washoff, "
            "seasonal LAI dynamics, and microclimate feedback."
        ),
    }


def estimate_cooling_effect(inp: FacadeGreeningInput) -> dict:
    """Summer afternoon facade-air temperature reduction (degC)."""
    if inp.facade_area_m2 <= 0:
        raise ValueError("facade_area_m2 must be > 0")
    low, high = COOLING_DELTA_T_RANGE_C
    scale = inp.coverage_fraction
    return {
        **_provenance(),
        "inputs": {
            "facade_area_m2": inp.facade_area_m2,
            "species": inp.species,
            "coverage_fraction": inp.coverage_fraction,
            "climate_zone": inp.climate_zone,
        },
        "delta_t_celsius": {
            "low": round(low * scale, 2),
            "high": round(high * scale, 2),
        },
        "scope": "near-facade air, summer afternoons",
        "notes": (
            "Range from published facade-greening field studies. "
            "Magnitude depends strongly on solar exposure, irrigation, "
            "and background wind. NOT a spatial simulation."
        ),
    }


def estimate_energy_savings(inp: FacadeGreeningInput) -> dict:
    """Indicative summer cooling-load reduction (fraction)."""
    if inp.facade_area_m2 <= 0:
        raise ValueError("facade_area_m2 must be > 0")
    low, high = ENERGY_COOLING_REDUCTION_RANGE
    scale = inp.coverage_fraction
    return {
        **_provenance(),
        "inputs": {
            "facade_area_m2": inp.facade_area_m2,
            "species": inp.species,
            "coverage_fraction": inp.coverage_fraction,
        },
        "summer_cooling_load_reduction_fraction": {
            "low": round(low * scale, 3),
            "high": round(high * scale, 3),
        },
        "notes": (
            "Indicative only. Real savings depend on building envelope, "
            "orientation, HVAC efficiency, and occupancy. Run a building "
            "energy model for design decisions."
        ),
    }


def full_advisory(inp: FacadeGreeningInput) -> dict:
    """Combined advisory bundle. Still NON-PALM, NON-COUPLED."""
    return {
        **_provenance(),
        "pollutant_uptake": estimate_pollutant_uptake(inp),
        "cooling_effect": estimate_cooling_effect(inp),
        "energy_savings": estimate_energy_savings(inp),
        "disclaimer": (
            "This is a literature-based first-order estimate. It is NOT "
            "a PALM/PALM-4U simulation result. A future PALM-coupled "
            "facade-greening module will be reported under a separate "
            "result_kind and must never be merged with these advisory "
            "outputs."
        ),
    }


def list_supported_species() -> list[dict]:
    return [
        {
            "id": sid,
            "lai_low": v[0],
            "lai_central": v[1],
            "lai_high": v[2],
        }
        for sid, v in SPECIES_LAI.items()
    ]
