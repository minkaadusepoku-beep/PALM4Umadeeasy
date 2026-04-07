"""Validation for custom meteorological forcing files.

In production, forcing files should be NetCDF with specific variables
(temperature, humidity, wind, radiation) and time dimensions.
In stub mode, we accept any file but perform basic size/extension checks.
"""

import os
from pathlib import Path

ALLOWED_EXTENSIONS = {".nc", ".nc4", ".netcdf"}
MAX_FILE_SIZE_MB = 500
REQUIRED_VARIABLES = ["pt", "qv", "u", "v"]  # PALM forcing variable names


def validate_forcing_file(file_path: Path, original_name: str) -> list[str]:
    """Validate a forcing file. Returns list of error messages (empty = valid)."""
    errors: list[str] = []

    # Extension check
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Invalid file extension '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Size check
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            errors.append(f"File too large ({size_mb:.1f} MB). Maximum: {MAX_FILE_SIZE_MB} MB")
        if file_path.stat().st_size == 0:
            errors.append("File is empty")

    # NetCDF content validation (only if netCDF4 is available)
    if not errors and ext in ALLOWED_EXTENSIONS:
        try:
            import netCDF4
            ds = netCDF4.Dataset(str(file_path), "r")
            try:
                # Check for required variables
                missing = [v for v in REQUIRED_VARIABLES if v not in ds.variables]
                if missing:
                    errors.append(f"Missing required variables: {', '.join(missing)}")

                # Check for time dimension
                if "time" not in ds.dimensions:
                    errors.append("Missing 'time' dimension")
            finally:
                ds.close()
        except ImportError:
            # netCDF4 not installed — skip deep validation (OK for dev/stub)
            pass
        except Exception as e:
            errors.append(f"Cannot read NetCDF file: {e}")

    return errors
