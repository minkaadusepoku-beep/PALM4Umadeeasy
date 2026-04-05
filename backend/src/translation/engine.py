"""
Translation layer orchestrator.

Converts a Scenario into the three files PALM needs:
  1. _p3d namelist (Fortran text)
  2. _static NetCDF (PIDS format)
  3. _dynamic NetCDF (forcing selection)
"""

from __future__ import annotations

from pathlib import Path

from ..models.scenario import Scenario
from .namelist import generate_namelist
from .static_driver import generate_static_driver
from .dynamic_driver import select_forcing


def translate_scenario(scenario: Scenario, output_dir: Path) -> dict[str, Path]:
    """
    Translate a scenario into PALM input files.

    Returns dict mapping file type to path:
      {"namelist": ..., "static_driver": ..., "dynamic_driver": ...}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    case_name = f"p4u_{scenario.fingerprint()}"

    namelist_path = output_dir / f"{case_name}_p3d"
    static_path = output_dir / f"{case_name}_static"
    dynamic_path = output_dir / f"{case_name}_dynamic"

    namelist_text = generate_namelist(scenario, case_name)
    namelist_path.write_text(namelist_text, encoding="utf-8")

    generate_static_driver(scenario, static_path)
    selected = select_forcing(scenario.simulation.forcing, dynamic_path)

    return {
        "namelist": namelist_path,
        "static_driver": static_path,
        "dynamic_driver": dynamic_path,
        "case_name": case_name,
    }
