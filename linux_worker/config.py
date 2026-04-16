"""Environment-driven configuration for the Linux PALM worker."""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


PALM_WORKER_TOKEN = _env("PALM_WORKER_TOKEN")
PALM_WORKER_JOBDIR = Path(_env("PALM_WORKER_JOBDIR", "/var/lib/palm_worker/jobs"))
# "stub" runs a placeholder echo for Phase A; "mpirun" runs real PALM.
PALM_WORKER_MODE = _env("PALM_WORKER_MODE", "stub").lower()
PALM_BINARY = _env("PALM_BINARY", "palm")
PALM_MPI_NP = int(_env("PALM_MPI_NP", "4") or "4")
PALM_VERSION_LABEL = _env("PALM_VERSION_LABEL", "23.10")
PALM_BUILD_FLAGS = _env("PALM_BUILD_FLAGS", "")
