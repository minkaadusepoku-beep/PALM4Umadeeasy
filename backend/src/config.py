"""Global configuration for PALM4Umadeeasy backend."""

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
