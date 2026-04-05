"""
Dynamic driver generation: select/generate forcing for PALM.

PHASE 1 STRUCTURAL PLACEHOLDER — variable names and dimensions are simplified
for pipeline testing only. Real PALM dynamic drivers require vertical profiles
(time, z) for init_atmosphere_pt/qv and use different variable naming conventions
depending on the forcing mode (dynamic input / large-scale forcing / nudging).
See palm/version_compat.md for the actual PIDS dynamic driver specification.

This module will require a rewrite when targeting real PALM execution (Phase 2).

Phase 1 approach: generate synthetic forcing profiles from archetype data
representative of NRW conditions. Values are plausible but not traceable
to specific DWD TRY datasets — treat as synthetic test data.

Phase 2 will add: vertical profiles, proper PIDS variable names, custom
forcing upload, and DWD Open Data integration.
"""

from __future__ import annotations

from pathlib import Path

import netCDF4 as nc
import numpy as np

from ..config import PALM_VERSION
from ..models.scenario import ForcingArchetype

# Synthetic archetype profiles representative of Cologne/NRW region.
# Each profile: hourly values for a 24h cycle starting at 06:00 local time.
# Values are plausible estimates, NOT traced to a specific DWD TRY dataset.
# Phase 2 will replace these with profiles derived from actual DWD TRY data.
ARCHETYPE_PROFILES = {
    ForcingArchetype.TYPICAL_HOT_DAY: {
        "label": "Typical Hot Summer Day (synthetic, NRW-representative)",
        "origin_time": "2025-07-15 06:00:00 +02",
        # Temperature [K] at 06:00, 07:00, ..., 05:00 next day
        "temperature_K": [
            293.15, 295.15, 298.15, 301.15, 303.15, 305.15, 306.15,
            306.65, 306.15, 305.15, 303.15, 301.15, 299.15, 297.65,
            296.65, 296.15, 295.65, 295.15, 294.65, 294.15, 293.65,
            293.35, 293.15, 293.05,
        ],
        # Specific humidity [kg/kg]
        "qv": [
            0.008, 0.008, 0.009, 0.009, 0.010, 0.010, 0.010,
            0.010, 0.010, 0.009, 0.009, 0.009, 0.008, 0.008,
            0.008, 0.008, 0.008, 0.008, 0.008, 0.008, 0.008,
            0.008, 0.008, 0.008,
        ],
        # Wind speed [m/s] at reference height
        "wind_u": [
            1.5, 2.0, 2.5, 3.0, 3.5, 3.5, 3.0, 2.5,
            2.5, 2.5, 2.0, 2.0, 1.5, 1.5, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5,
        ],
        "surface_pressure_Pa": 101325.0,
    },
    ForcingArchetype.HEAT_WAVE_DAY: {
        "label": "Heat Wave Day (synthetic, NRW-representative, +3K anomaly)",
        "origin_time": "2025-07-25 06:00:00 +02",
        "temperature_K": [
            296.15, 298.15, 301.15, 304.15, 306.15, 308.15, 309.15,
            309.65, 309.15, 308.15, 306.15, 304.15, 302.15, 300.65,
            299.65, 299.15, 298.65, 298.15, 297.65, 297.15, 296.65,
            296.35, 296.15, 296.05,
        ],
        "qv": [
            0.009, 0.009, 0.010, 0.010, 0.011, 0.011, 0.011,
            0.011, 0.011, 0.010, 0.010, 0.010, 0.009, 0.009,
            0.009, 0.009, 0.009, 0.009, 0.009, 0.009, 0.009,
            0.009, 0.009, 0.009,
        ],
        "wind_u": [
            1.0, 1.5, 2.0, 2.5, 2.5, 2.5, 2.0, 2.0,
            2.0, 2.0, 1.5, 1.5, 1.0, 1.0, 0.5, 0.5,
            0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0,
        ],
        "surface_pressure_Pa": 101600.0,
    },
    ForcingArchetype.MODERATE_SUMMER_DAY: {
        "label": "Moderate Summer Day (synthetic, NRW-representative)",
        "origin_time": "2025-06-20 06:00:00 +02",
        "temperature_K": [
            289.15, 291.15, 293.15, 295.15, 297.15, 298.15, 299.15,
            299.65, 299.15, 298.15, 296.15, 294.15, 292.15, 291.15,
            290.65, 290.15, 289.65, 289.15, 288.65, 288.15, 288.15,
            288.15, 289.15, 289.15,
        ],
        "qv": [
            0.007, 0.007, 0.007, 0.008, 0.008, 0.008, 0.008,
            0.008, 0.008, 0.008, 0.007, 0.007, 0.007, 0.007,
            0.007, 0.007, 0.007, 0.007, 0.007, 0.007, 0.007,
            0.007, 0.007, 0.007,
        ],
        "wind_u": [
            2.0, 2.5, 3.0, 3.5, 4.0, 4.0, 3.5, 3.5,
            3.0, 3.0, 2.5, 2.5, 2.0, 2.0, 2.0, 1.5,
            1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 2.0, 2.0,
        ],
        "surface_pressure_Pa": 101325.0,
    },
    ForcingArchetype.WARM_NIGHT: {
        "label": "Warm Tropical Night (synthetic, NRW-representative, Tmin >= 20C)",
        "origin_time": "2025-07-20 18:00:00 +02",
        "temperature_K": [
            303.15, 301.15, 299.65, 298.15, 297.15, 296.15, 295.65,
            295.15, 294.65, 294.15, 293.65, 293.15, 294.15, 296.15,
            298.15, 300.15, 302.15, 303.15, 304.15, 304.65, 304.15,
            303.15, 302.15, 301.15,
        ],
        "qv": [
            0.011, 0.011, 0.010, 0.010, 0.010, 0.010, 0.010,
            0.010, 0.010, 0.010, 0.009, 0.009, 0.009, 0.010,
            0.010, 0.010, 0.011, 0.011, 0.011, 0.011, 0.011,
            0.011, 0.011, 0.011,
        ],
        "wind_u": [
            1.5, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5,
            0.5, 0.5, 0.5, 0.5, 1.0, 1.5, 2.0, 2.5,
            2.5, 2.5, 2.0, 2.0, 1.5, 1.5, 1.5, 1.5,
        ],
        "surface_pressure_Pa": 101200.0,
    },
}


def select_forcing(archetype: ForcingArchetype, output_path: Path) -> dict:
    """
    Generate a PALM dynamic driver NetCDF for the given forcing archetype.

    Returns metadata dict about the selected forcing.
    """
    profile = ARCHETYPE_PROFILES[archetype]
    _write_dynamic_driver(profile, output_path)
    return {
        "archetype": archetype.value,
        "label": profile["label"],
        "origin_time": profile["origin_time"],
        "path": str(output_path),
    }


def _write_dynamic_driver(profile: dict, output_path: Path) -> None:
    """Write PALM dynamic driver NetCDF from an archetype profile."""
    n_time = len(profile["temperature_K"])
    times = np.arange(n_time, dtype=np.float64) * 3600.0  # seconds since origin

    with nc.Dataset(str(output_path), "w", format="NETCDF4") as ds:
        ds.Conventions = "CF-1.7"
        ds.palm_version = int(PALM_VERSION.split(".")[0])
        ds.origin_time = profile["origin_time"]

        ds.createDimension("time", n_time)

        # Time coordinate
        tv = ds.createVariable("time", "f8", ("time",))
        tv.units = "seconds since " + profile["origin_time"]
        tv.calendar = "proleptic_gregorian"
        tv[:] = times

        # Initial potential temperature profile (surface value)
        init_pt = ds.createVariable("init_atmosphere_pt", "f4", ("time",))
        init_pt.units = "K"
        init_pt.long_name = "initial potential temperature"
        init_pt[:] = np.array(profile["temperature_K"], dtype=np.float32)

        # Specific humidity
        init_qv = ds.createVariable("init_atmosphere_qv", "f4", ("time",))
        init_qv.units = "kg kg-1"
        init_qv.long_name = "initial specific humidity"
        init_qv[:] = np.array(profile["qv"], dtype=np.float32)

        # Large-scale forcing: u-component wind
        ls_u = ds.createVariable("ls_forcing_ug", "f4", ("time",))
        ls_u.units = "m s-1"
        ls_u.long_name = "geostrophic wind u-component"
        ls_u[:] = np.array(profile["wind_u"], dtype=np.float32)

        # v-component: zero (wind from west assumed)
        ls_v = ds.createVariable("ls_forcing_vg", "f4", ("time",))
        ls_v.units = "m s-1"
        ls_v.long_name = "geostrophic wind v-component"
        ls_v[:] = np.zeros(n_time, dtype=np.float32)

        # Surface pressure
        sp = ds.createVariable("surface_forcing_surface_pressure", "f4", ("time",))
        sp.units = "Pa"
        sp.long_name = "surface pressure"
        sp[:] = np.full(n_time, profile["surface_pressure_Pa"], dtype=np.float32)
