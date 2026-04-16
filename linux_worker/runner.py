"""
PALM execution for the Linux worker.

Two modes, selected by ``PALM_WORKER_MODE``:

- ``stub``   — Phase A. Echo the static driver back as a placeholder output so
               the wire protocol can be tested without a compiled PALM.
- ``mpirun`` — Phase B. Run ``mpirun -np $PALM_MPI_NP $PALM_BINARY <case>``
               inside ``input_dir`` and let PALM write outputs.

Anything that doesn't fit one of those two raises ``RunnerError`` — callers
(the FastAPI layer) translate that into an HTTP 500 or a failed job record.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class RunnerError(RuntimeError):
    """Raised when a PALM run cannot be started or completes with a non-zero exit."""


def execute_palm(
    case_name: str,
    input_dir: Path,
    output_dir: Path,
    mode: str = "stub",
    palm_binary: str = "palm",
    mpi_np: int = 4,
) -> None:
    """
    Execute PALM for ``case_name`` with inputs in ``input_dir``.

    The contract is: on successful return, ``output_dir`` contains the files
    the client should receive. On failure, raise ``RunnerError`` with a
    human-readable message.
    """
    mode = (mode or "stub").lower()

    if mode == "stub":
        _run_stub(case_name, input_dir, output_dir)
        return
    if mode == "mpirun":
        _run_mpirun(case_name, input_dir, output_dir, palm_binary, mpi_np)
        return

    raise RunnerError(f"Unknown PALM_WORKER_MODE: {mode!r}")


# ---------------------------------------------------------------------------
# Phase A — stub
# ---------------------------------------------------------------------------


def _run_stub(case_name: str, input_dir: Path, output_dir: Path) -> None:
    """
    Placeholder runner for Phase A.

    Copies the static driver into ``output_dir`` as ``<case>_av_3d.nc`` so the
    client's post-processor finds a file at the expected key. The payload is
    not a real PALM output; this only exists to exercise the HTTP protocol
    before PALM is compiled on the Linux host.
    """
    static_driver = input_dir / f"{case_name}_static.nc"
    if not static_driver.exists():
        # Fall back to any .nc file in the bundle.
        candidates = sorted(input_dir.glob("*_static.nc")) or sorted(
            input_dir.glob("*.nc")
        )
        if not candidates:
            raise RunnerError(
                f"Stub runner could not find a static driver for case {case_name!r}"
            )
        static_driver = candidates[0]

    dest = output_dir / f"{case_name}_av_3d.nc"
    shutil.copyfile(static_driver, dest)

    marker = output_dir / "STUB_README.txt"
    marker.write_text(
        "This output was produced by the Linux worker in stub mode.\n"
        "It is a placeholder copy of the static driver — not a real PALM run.\n"
        "Set PALM_WORKER_MODE=mpirun and compile PALM to produce real outputs.\n"
    )


# ---------------------------------------------------------------------------
# Phase B — real mpirun palm
# ---------------------------------------------------------------------------


def _run_mpirun(
    case_name: str,
    input_dir: Path,
    output_dir: Path,
    palm_binary: str,
    mpi_np: int,
) -> None:
    """
    Run PALM via ``mpirun`` inside ``input_dir`` and move outputs to ``output_dir``.

    Not exercised on CI/Windows. Activation criteria are in ADR-005 Phase B.
    """
    cmd = ["mpirun", "-np", str(mpi_np), palm_binary, case_name]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(input_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RunnerError(f"mpirun or palm not on PATH: {exc}") from exc

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-50:]
        raise RunnerError(
            f"PALM exited with code {proc.returncode}. Tail:\n" + "\n".join(tail)
        )

    # PALM writes under the working directory; collect everything that looks
    # like a NetCDF output into output_dir. The client is tolerant about
    # filenames (see remote_client._classify_output) so we don't enforce a
    # specific layout here.
    for produced in input_dir.glob("*.nc"):
        # Skip the inputs we uploaded.
        if produced.name.endswith(("_static.nc", "_dynamic.nc")):
            continue
        shutil.move(str(produced), str(output_dir / produced.name))

    # Also carry across the PALM log file if present, for debugging.
    for log in input_dir.glob("RUN_*"):
        if log.is_file():
            shutil.copy2(str(log), str(output_dir / log.name))
