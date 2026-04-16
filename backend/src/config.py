"""Global configuration for PALM4Umadeeasy backend."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = Path(__file__).parent.parent
CATALOGUE_DIR = PROJECT_ROOT / "catalogues"
PALM_DIR = PROJECT_ROOT / "palm"
FORCING_DIR = PALM_DIR / "forcing_templates"
REPORT_TEMPLATE_DIR = Path(__file__).parent / "reporting" / "templates"

SCHEMA_VERSION = "1.0.0"
PALM_VERSION = "23.10"

# Default grid configuration (ADR-003: dz=2m near ground for bio-met at ~1.0m)
DEFAULT_DZ = 2.0
DEFAULT_DZ_STRETCH_LEVEL = 50.0
DEFAULT_NZ = 40

# Bio-met output height target (VDI 3787: 1.1m, hardcoded in PALM)
BIOMET_TARGET_HEIGHT_M = 1.1

# --- PALM execution backend (ADR-005) --------------------------------------
# PALM_RUNNER_MODE selects how run_palm() dispatches:
#   "stub"   — synthetic NetCDF generator (default, Windows-safe)
#   "remote" — HTTP to a Linux worker; requires PALM_REMOTE_URL + PALM_REMOTE_TOKEN
#   "local"  — in-process mpirun on the current (Linux) host
PALM_RUNNER_MODE = os.environ.get("PALM_RUNNER_MODE", "stub").strip().lower()
PALM_REMOTE_URL = os.environ.get("PALM_REMOTE_URL", "").strip()
PALM_REMOTE_TOKEN = os.environ.get("PALM_REMOTE_TOKEN", "").strip()
# Poll cadence (seconds) the remote client uses while waiting on the Linux worker.
PALM_REMOTE_POLL_INTERVAL_S = float(os.environ.get("PALM_REMOTE_POLL_INTERVAL_S", "5"))
# Hard cap on how long the remote client will wait for a single run (seconds).
PALM_REMOTE_TIMEOUT_S = float(os.environ.get("PALM_REMOTE_TIMEOUT_S", "7200"))
