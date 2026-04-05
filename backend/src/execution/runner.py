"""
PALM execution runner.

Phase 1: stubbed for Windows development. Generates synthetic output
matching PALM's output format so the full spine can be tested end-to-end.

Phase 2: real PALM submission via SSH/Slurm on a Linux cloud VM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import netCDF4 as nc
import numpy as np

from ..config import BIOMET_TARGET_HEIGHT_M


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STUBBED = "stubbed"


@dataclass
class RunResult:
    status: RunStatus
    case_name: str
    output_dir: Path
    output_files: dict[str, Path]
    message: str = ""
    wall_time_s: Optional[float] = None


def run_palm(
    case_name: str,
    input_files: dict[str, Path],
    output_dir: Path,
    stub: bool = True,
    seed: int = 0,
) -> RunResult:
    """
    Execute a PALM simulation.

    Args:
        case_name: PALM case name (used for file naming)
        input_files: dict with keys "namelist", "static_driver", "dynamic_driver"
        output_dir: directory to write PALM output
        stub: if True, generate synthetic output (Windows dev mode)
        seed: RNG seed for deterministic stub output (derived from scenario fingerprint)

    Returns:
        RunResult with status and output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if stub:
        return _run_stub(case_name, input_files, output_dir, seed=seed)

    # Phase 2: real PALM execution
    raise NotImplementedError(
        "Real PALM execution requires a Linux environment with PALM compiled. "
        "Set stub=True for development, or implement SSH/Slurm submission."
    )


def _run_stub(
    case_name: str, input_files: dict[str, Path], output_dir: Path, seed: int = 0,
) -> RunResult:
    """Generate synthetic PALM-like output for end-to-end testing."""
    static_path = input_files["static_driver"]

    # Read domain dimensions from static driver
    with nc.Dataset(str(static_path), "r") as ds:
        nx = len(ds.dimensions["x"])
        ny = len(ds.dimensions["y"])
        x_coords = ds.variables["x"][:]
        y_coords = ds.variables["y"][:]

    # Generate synthetic bio-met output (seeded for determinism)
    av3d_path = output_dir / f"{case_name}_av_3d.nc"
    _generate_synthetic_biomet(av3d_path, nx, ny, x_coords, y_coords, seed=seed)

    return RunResult(
        status=RunStatus.STUBBED,
        case_name=case_name,
        output_dir=output_dir,
        output_files={
            "av_3d": av3d_path,
        },
        message="Stub output: synthetic bio-met fields. Not from actual PALM simulation.",
        wall_time_s=0.0,
    )


def _generate_synthetic_biomet(
    output_path: Path, nx: int, ny: int,
    x_coords: np.ndarray, y_coords: np.ndarray,
    seed: int = 0,
) -> None:
    """
    Generate synthetic bio-met output resembling PALM's av_3d file.

    Creates spatially varying PET, UTCI, MRT fields with realistic ranges
    and urban heat island patterns for testing the downstream pipeline.

    Seeded RNG ensures deterministic output for the same scenario fingerprint.
    """
    rng = np.random.default_rng(seed)
    n_times = 6  # 6 output timesteps
    times = np.arange(n_times) * 1800.0  # every 30 min

    with nc.Dataset(str(output_path), "w", format="NETCDF4") as ds:
        ds.Conventions = "CF-1.7"
        ds.source = "PALM4Umadeeasy stub generator (NOT a real PALM simulation)"

        ds.createDimension("time", n_times)
        ds.createDimension("x", nx)
        ds.createDimension("y", ny)

        tv = ds.createVariable("time", "f8", ("time",))
        tv.units = "seconds since simulation start"
        tv[:] = times

        xv = ds.createVariable("x", "f4", ("x",))
        xv.units = "m"
        xv[:] = x_coords

        yv = ds.createVariable("y", "f4", ("y",))
        yv.units = "m"
        yv[:] = y_coords

        # Synthetic spatial pattern: radial gradient from center (urban heat island)
        cx, cy = nx // 2, ny // 2
        yy, xx = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2) + 1e-6
        spatial = dist / max_dist  # 0 at center, ~1 at corners

        # PET: 25-42 C range, hotter in center (UHI), warming over time
        pet = ds.createVariable("bio_pet*", "f4", ("time", "y", "x"), fill_value=-9999.0)
        pet.units = "degree_C"
        pet.long_name = "physiological equivalent temperature"
        for t in range(n_times):
            base = 30.0 + 5.0 * (t / n_times)  # warming trend
            field = base - 8.0 * spatial + rng.normal(0, 0.5, (ny, nx))
            pet[t, :, :] = np.clip(field, 20.0, 50.0).astype(np.float32)

        # UTCI: similar pattern, slightly different range
        utci = ds.createVariable("bio_utci*", "f4", ("time", "y", "x"), fill_value=-9999.0)
        utci.units = "degree_C"
        utci.long_name = "universal thermal climate index"
        for t in range(n_times):
            base = 32.0 + 5.0 * (t / n_times)
            field = base - 7.0 * spatial + rng.normal(0, 0.5, (ny, nx))
            utci[t, :, :] = np.clip(field, 22.0, 52.0).astype(np.float32)

        # MRT: mean radiant temperature
        mrt = ds.createVariable("bio_mrt*", "f4", ("time", "y", "x"), fill_value=-9999.0)
        mrt.units = "degree_C"
        mrt.long_name = "mean radiant temperature"
        for t in range(n_times):
            base = 45.0 + 8.0 * (t / n_times)
            field = base - 10.0 * spatial + rng.normal(0, 1.0, (ny, nx))
            mrt[t, :, :] = np.clip(field, 30.0, 70.0).astype(np.float32)

        # Surface temperature
        tsurf = ds.createVariable("t_surface*", "f4", ("time", "y", "x"), fill_value=-9999.0)
        tsurf.units = "K"
        tsurf.long_name = "surface temperature"
        for t in range(n_times):
            base = 315.0 + 3.0 * (t / n_times)
            field = base - 5.0 * spatial + rng.normal(0, 0.5, (ny, nx))
            tsurf[t, :, :] = np.clip(field, 300.0, 340.0).astype(np.float32)
