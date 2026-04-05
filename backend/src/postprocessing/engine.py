"""
Post-processing engine: extract comfort indices from PALM output.

Reads PALM's averaged 3D output NetCDF, extracts bio-met variables at
the diagnostic height (1.1m AGL per VDI 3787 / ADR-003), computes
statistics, and classifies thermal comfort.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import netCDF4 as nc
import numpy as np

from ..config import BIOMET_TARGET_HEIGHT_M
from ..catalogues.loader import classify_pet
from pythermalcomfort.models import pet_steady


@dataclass
class ComfortField:
    """A 2D comfort field at diagnostic height for one timestep."""
    variable: str
    units: str
    time_s: float
    data: np.ndarray  # shape (ny, nx)


@dataclass
class ComfortStatistics:
    """Statistics for a comfort variable across the domain."""
    variable: str
    mean: float
    median: float
    std: float
    p05: float
    p95: float
    min_val: float
    max_val: float
    n_valid: int


@dataclass
class PETClassification:
    """Fraction of domain area in each VDI 3787 comfort class."""
    class_fractions: dict[str, float]  # perception -> fraction (0-1)
    dominant_class: str
    stress_level: str


@dataclass
class PETVerification:
    """Cross-validation of PALM's built-in PET against pythermalcomfort."""
    mean_absolute_error: float
    max_absolute_error: float
    n_points: int
    within_1K: float  # fraction of cells within 1K agreement
    palm_mean: float
    recomputed_mean: float


@dataclass
class PostProcessingResult:
    """Complete post-processing output for one scenario run."""
    case_name: str
    fields: dict[str, list[ComfortField]]  # variable -> list of timestep fields
    statistics: dict[str, ComfortStatistics]  # variable -> time-averaged stats
    pet_classification: Optional[PETClassification] = None
    pet_verification: Optional[PETVerification] = None
    x_coords: Optional[np.ndarray] = None
    y_coords: Optional[np.ndarray] = None
    metadata: dict = field(default_factory=dict)


# Variables to extract from PALM output
BIOMET_VARIABLES = {
    "bio_pet*": {"long_name": "PET", "units": "degree_C"},
    "bio_utci*": {"long_name": "UTCI", "units": "degree_C"},
    "bio_mrt*": {"long_name": "MRT", "units": "degree_C"},
    "t_surface*": {"long_name": "Surface Temperature", "units": "K"},
}


def postprocess_run(case_name: str, output_files: dict[str, Path]) -> PostProcessingResult:
    """
    Extract and analyze comfort indices from PALM output.

    Args:
        case_name: PALM case name
        output_files: dict mapping file type to path (from runner)

    Returns:
        PostProcessingResult with extracted fields, statistics, and classification.
    """
    av3d_path = output_files.get("av_3d")
    if av3d_path is None or not av3d_path.exists():
        raise FileNotFoundError(f"No averaged 3D output found for {case_name}")

    fields = {}
    x_coords = None
    y_coords = None

    with nc.Dataset(str(av3d_path), "r") as ds:
        times = ds.variables["time"][:]
        x_coords = ds.variables["x"][:]
        y_coords = ds.variables["y"][:]

        for var_name, var_meta in BIOMET_VARIABLES.items():
            if var_name not in ds.variables:
                continue

            var_data = ds.variables[var_name]
            timestep_fields = []

            for t_idx, t_val in enumerate(times):
                if var_data.ndim == 3:
                    # (time, y, x) — already at diagnostic height
                    data_2d = var_data[t_idx, :, :]
                elif var_data.ndim == 4:
                    # (time, z, y, x) — select nearest level to 1.1m
                    z_coords = ds.variables["z"][:] if "z" in ds.variables else np.array([1.0])
                    z_idx = int(np.argmin(np.abs(z_coords - BIOMET_TARGET_HEIGHT_M)))
                    data_2d = var_data[t_idx, z_idx, :, :]
                else:
                    continue

                data_2d = np.ma.filled(data_2d, np.nan)
                timestep_fields.append(ComfortField(
                    variable=var_name,
                    units=var_meta["units"],
                    time_s=float(t_val),
                    data=np.array(data_2d, dtype=np.float32),
                ))

            if timestep_fields:
                fields[var_name] = timestep_fields

    # Compute time-averaged statistics
    statistics = {}
    for var_name, var_fields in fields.items():
        all_data = np.stack([f.data for f in var_fields], axis=0)
        time_mean = np.nanmean(all_data, axis=0)
        valid = time_mean[~np.isnan(time_mean)]

        if len(valid) > 0:
            statistics[var_name] = ComfortStatistics(
                variable=var_name,
                mean=float(np.mean(valid)),
                median=float(np.median(valid)),
                std=float(np.std(valid)),
                p05=float(np.percentile(valid, 5)),
                p95=float(np.percentile(valid, 95)),
                min_val=float(np.min(valid)),
                max_val=float(np.max(valid)),
                n_valid=int(len(valid)),
            )

    # PET classification (time-averaged)
    pet_classification = None
    if "bio_pet*" in fields:
        pet_classification = _classify_pet_domain(fields["bio_pet*"])

    return PostProcessingResult(
        case_name=case_name,
        fields=fields,
        statistics=statistics,
        pet_classification=pet_classification,
        x_coords=x_coords,
        y_coords=y_coords,
        metadata={
            "biomet_height_m": BIOMET_TARGET_HEIGHT_M,
            "n_timesteps": len(next(iter(fields.values()))) if fields else 0,
        },
    )


def _classify_pet_domain(pet_fields: list[ComfortField]) -> PETClassification:
    """Classify PET across domain using VDI 3787 thresholds."""
    all_data = np.stack([f.data for f in pet_fields], axis=0)
    time_mean = np.nanmean(all_data, axis=0)
    valid = time_mean[~np.isnan(time_mean)]

    if len(valid) == 0:
        return PETClassification(
            class_fractions={},
            dominant_class="Unknown",
            stress_level="Unknown",
        )

    class_counts: dict[str, int] = {}
    for val in valid.flat:
        result = classify_pet(float(val))
        perception = result["perception"]
        class_counts[perception] = class_counts.get(perception, 0) + 1

    total = sum(class_counts.values())
    class_fractions = {k: v / total for k, v in class_counts.items()}

    dominant = max(class_fractions, key=class_fractions.get)
    stress = classify_pet(float(np.median(valid)))["stress"]

    return PETClassification(
        class_fractions=class_fractions,
        dominant_class=dominant,
        stress_level=stress,
    )


def recompute_pet_from_raw(
    ta_C: np.ndarray,
    mrt_C: np.ndarray,
    wind_ms: np.ndarray,
    rh_pct: np.ndarray,
) -> np.ndarray:
    """
    Independently recompute PET from raw meteorological fields using pythermalcomfort.

    Used to cross-validate PALM's built-in bio_pet* output against an independent
    implementation (Walther & Goestchel 2018 correction).

    Args:
        ta_C: air temperature [degC], 2D array (ny, nx)
        mrt_C: mean radiant temperature [degC], 2D array (ny, nx)
        wind_ms: wind speed [m/s], 2D array (ny, nx)
        rh_pct: relative humidity [%], 2D array (ny, nx)

    Returns:
        PET values [degC], same shape as input arrays.
    """
    result = np.full_like(ta_C, np.nan, dtype=np.float32)
    ny, nx = ta_C.shape
    for j in range(ny):
        for i in range(nx):
            ta = float(ta_C[j, i])
            mrt = float(mrt_C[j, i])
            v = max(float(wind_ms[j, i]), 0.1)  # pet_steady requires v > 0
            rh = float(rh_pct[j, i])
            if np.isnan(ta) or np.isnan(mrt) or np.isnan(v) or np.isnan(rh):
                continue
            try:
                result[j, i] = pet_steady(
                    tdb=ta, tr=mrt, v=v, rh=rh,
                    met=1.4, clo=0.5, position="standing",
                    age=35, weight=75, height=1.80,
                )
            except Exception:
                pass
    return result


def verify_pet(
    palm_pet_fields: list[ComfortField],
    mrt_fields: list[ComfortField],
    ta_C: float,
    rh_pct: float,
    wind_ms: float,
) -> PETVerification:
    """
    Verify PALM's PET output against pythermalcomfort recomputation.

    For stub mode, uses scalar met values (from forcing archetype) since
    PALM stub doesn't output theta/humidity grids. For real PALM runs,
    these should be extracted from the output NetCDF.

    Args:
        palm_pet_fields: PET fields from PALM output
        mrt_fields: MRT fields from PALM output
        ta_C: air temperature [degC] (scalar for stub, will be broadcast)
        rh_pct: relative humidity [%] (scalar for stub)
        wind_ms: wind speed [m/s] (scalar for stub)

    Returns:
        PETVerification with error statistics.
    """
    palm_mean_2d = np.nanmean(np.stack([f.data for f in palm_pet_fields], axis=0), axis=0)
    mrt_mean_2d = np.nanmean(np.stack([f.data for f in mrt_fields], axis=0), axis=0)

    ny, nx = palm_mean_2d.shape
    ta_arr = np.full((ny, nx), ta_C, dtype=np.float32)
    rh_arr = np.full((ny, nx), rh_pct, dtype=np.float32)
    wind_arr = np.full((ny, nx), wind_ms, dtype=np.float32)

    recomputed = recompute_pet_from_raw(ta_arr, mrt_mean_2d, wind_arr, rh_arr)

    valid_mask = ~(np.isnan(palm_mean_2d) | np.isnan(recomputed))
    palm_valid = palm_mean_2d[valid_mask]
    recomp_valid = recomputed[valid_mask]
    n = len(palm_valid)

    if n == 0:
        return PETVerification(
            mean_absolute_error=float("nan"),
            max_absolute_error=float("nan"),
            n_points=0,
            within_1K=0.0,
            palm_mean=float("nan"),
            recomputed_mean=float("nan"),
        )

    abs_errors = np.abs(palm_valid - recomp_valid)
    return PETVerification(
        mean_absolute_error=float(np.mean(abs_errors)),
        max_absolute_error=float(np.max(abs_errors)),
        n_points=n,
        within_1K=float(np.sum(abs_errors <= 1.0) / n),
        palm_mean=float(np.mean(palm_valid)),
        recomputed_mean=float(np.mean(recomp_valid)),
    )
