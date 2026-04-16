"""
PALM execution runner.

Dispatches to one of three backends based on ``PALM_RUNNER_MODE`` (or the
legacy ``stub`` boolean kept for backward compatibility):

- ``stub``   — synthetic NetCDF generator for Windows-only development and CI
- ``remote`` — POST inputs to a remote Linux worker (see ADR-005), poll, download
- ``local``  — run ``mpirun palm`` directly in-process (Linux-only)

See ``docs/decisions/ADR-005-windows-prep-linux-worker.md`` for the architectural
decision behind the split.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import netCDF4 as nc
import numpy as np

from ..config import (
    BIOMET_TARGET_HEIGHT_M,
)


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STUBBED = "stubbed"


class RunnerMode(str, Enum):
    STUB = "stub"
    REMOTE = "remote"
    LOCAL = "local"


@dataclass
class RunResult:
    status: RunStatus
    case_name: str
    output_dir: Path
    output_files: dict[str, Path]
    message: str = ""
    wall_time_s: Optional[float] = None
    # Reproducibility metadata: populated by remote/local backends with the
    # exact PALM version/build flags reported by the Linux worker. Stub runs
    # leave this as None.
    palm_version: Optional[str] = None
    palm_build_flags: Optional[str] = None


def _resolve_mode(stub: Optional[bool], mode: Optional[str | RunnerMode]) -> RunnerMode:
    """
    Determine the effective runner mode.

    Precedence (high → low):
    1. Explicit ``mode`` argument
    2. Legacy ``stub`` boolean (True → STUB; False → fall through)
    3. Resolved runtime config (DB row preferred, else env, else default)
       — see ``settings.load_config_sync``.
    """
    if mode is not None:
        return RunnerMode(mode) if not isinstance(mode, RunnerMode) else mode
    if stub is True:
        return RunnerMode.STUB

    # Lazy import to avoid a circular import at module load — settings.py
    # imports from ..db.models which doesn't depend on runner.
    from .settings import load_config_sync

    resolved = load_config_sync()
    if stub is False:
        # Caller explicitly disabled stub but didn't pick a mode: respect the
        # resolved config, but if it still says stub, assume they meant local.
        effective = RunnerMode(resolved.mode)
        return effective if effective != RunnerMode.STUB else RunnerMode.LOCAL
    return RunnerMode(resolved.mode)


def run_palm(
    case_name: str,
    input_files: dict[str, Path],
    output_dir: Path,
    stub: Optional[bool] = True,
    seed: int = 0,
    mode: Optional[str | RunnerMode] = None,
) -> RunResult:
    """
    Execute a PALM simulation.

    Args:
        case_name: PALM case name (used for file naming)
        input_files: dict with keys "namelist", "static_driver", "dynamic_driver"
        output_dir: directory to write PALM output
        stub: legacy flag; True forces the synthetic generator, False defers to
              ``mode``/``PALM_RUNNER_MODE``. Kept so existing callers don't break.
        seed: RNG seed for deterministic stub output (derived from scenario fingerprint)
        mode: explicit runner mode; overrides ``stub`` and the env default.

    Returns:
        RunResult with status and output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_mode = _resolve_mode(stub, mode)

    if effective_mode == RunnerMode.STUB:
        return _run_stub(case_name, input_files, output_dir, seed=seed)
    if effective_mode == RunnerMode.REMOTE:
        return _run_remote(case_name, input_files, output_dir)
    if effective_mode == RunnerMode.LOCAL:
        return _run_local(case_name, input_files, output_dir)

    raise ValueError(f"Unknown runner mode: {effective_mode!r}")


def _run_remote(
    case_name: str, input_files: dict[str, Path], output_dir: Path,
) -> RunResult:
    """Delegate execution to a remote Linux worker (see ADR-005)."""
    # Imported lazily so stub-only tests don't require httpx at import time.
    from .remote_client import RemoteRunnerClient, RemoteRunnerError
    from .settings import load_config_sync

    resolved = load_config_sync()
    if not resolved.remote_url:
        raise RuntimeError(
            "PALM runner mode is 'remote' but no worker URL is configured. "
            "Set it in the admin panel (/admin) or via PALM_REMOTE_URL."
        )
    if not resolved.remote_token:
        raise RuntimeError(
            "PALM runner mode is 'remote' but no bearer token is configured. "
            "Set it in the admin panel (/admin) or via PALM_REMOTE_TOKEN."
        )

    client = RemoteRunnerClient(
        base_url=resolved.remote_url,
        token=resolved.remote_token,
    )
    try:
        return client.run(case_name, input_files, output_dir)
    except RemoteRunnerError as exc:
        return RunResult(
            status=RunStatus.FAILED,
            case_name=case_name,
            output_dir=output_dir,
            output_files={},
            message=f"Remote PALM worker error: {exc}",
        )


def _run_local(
    case_name: str, input_files: dict[str, Path], output_dir: Path,
) -> RunResult:
    """
    Run ``mpirun palm`` directly on the current (Linux) host.

    Stubbed until PALM is compiled on the target Linux machine. See ADR-005
    Phase B for the activation criteria.
    """
    raise NotImplementedError(
        "Local PALM execution requires a Linux environment with PALM compiled. "
        "This branch is activated in ADR-005 Phase B. For now use stub or remote mode."
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
