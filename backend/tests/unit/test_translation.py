"""
Unit tests for the translation layer.

Verifies that namelist, static driver, and dynamic driver generation
produce valid, deterministic output.
"""

import pytest
import sys
import tempfile
from pathlib import Path

import netCDF4 as nc

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.translation.namelist import generate_namelist
from src.translation.static_driver import generate_static_driver
from src.translation.dynamic_driver import select_forcing
from src.translation.engine import translate_scenario
from src.models.scenario import ForcingArchetype
from tests.fixtures.scenarios import make_valid_baseline, make_valid_intervention


class TestNamelist:
    def test_generates_valid_namelist(self):
        scenario = make_valid_baseline()
        text = generate_namelist(scenario, "test_case")
        assert "&initialization_parameters" in text
        assert "&runtime_parameters" in text
        assert "&biometeorology_parameters" in text
        assert "nx =" in text
        assert "ny =" in text

    def test_deterministic_output(self):
        scenario = make_valid_baseline()
        text1 = generate_namelist(scenario, "test_case")
        text2 = generate_namelist(scenario, "test_case")
        assert text1 == text2

    def test_nx_ny_zero_indexed(self):
        scenario = make_valid_baseline()
        text = generate_namelist(scenario, "test_case")
        # nx in namelist should be domain.nx - 1
        expected_nx = scenario.domain.nx - 1
        assert f"nx = {expected_nx}" in text

    def test_contains_fingerprint(self):
        scenario = make_valid_baseline()
        text = generate_namelist(scenario, "test_case")
        assert scenario.fingerprint() in text


class TestStaticDriver:
    def test_generates_valid_netcdf(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_static"
            generate_static_driver(scenario, path)
            assert path.exists()

            with nc.Dataset(str(path), "r") as ds:
                assert "x" in ds.dimensions
                assert "y" in ds.dimensions
                assert "vegetation_type" in ds.variables
                assert "pavement_type" in ds.variables
                assert "zt" in ds.variables

    def test_tree_lad_written(self):
        scenario = make_valid_intervention()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_static"
            generate_static_driver(scenario, path)

            with nc.Dataset(str(path), "r") as ds:
                assert "lad" in ds.variables
                assert "zlad" in ds.dimensions

    def test_deterministic_output(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "static1"
            p2 = Path(tmpdir) / "static2"
            generate_static_driver(scenario, p1)
            generate_static_driver(scenario, p2)

            import numpy as np
            with nc.Dataset(str(p1), "r") as ds1, nc.Dataset(str(p2), "r") as ds2:
                for var_name in ds1.variables:
                    np.testing.assert_array_equal(
                        ds1.variables[var_name][:],
                        ds2.variables[var_name][:],
                        err_msg=f"Static driver variable '{var_name}' is non-deterministic",
                    )

    def test_dynamic_driver_deterministic(self):
        """Dynamic driver must be byte-identical for the same forcing archetype."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import numpy as np
            p1 = Path(tmpdir) / "dyn1"
            p2 = Path(tmpdir) / "dyn2"
            select_forcing(ForcingArchetype.TYPICAL_HOT_DAY, p1)
            select_forcing(ForcingArchetype.TYPICAL_HOT_DAY, p2)

            with nc.Dataset(str(p1), "r") as ds1, nc.Dataset(str(p2), "r") as ds2:
                for var_name in ds1.variables:
                    np.testing.assert_array_equal(
                        ds1.variables[var_name][:],
                        ds2.variables[var_name][:],
                        err_msg=f"Dynamic driver variable '{var_name}' is non-deterministic",
                    )


class TestDynamicDriver:
    @pytest.mark.parametrize("archetype", list(ForcingArchetype))
    def test_generates_all_archetypes(self, archetype):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_dynamic"
            result = select_forcing(archetype, path)
            assert path.exists()
            assert result["archetype"] == archetype.value

            with nc.Dataset(str(path), "r") as ds:
                assert "time" in ds.dimensions
                assert "init_atmosphere_pt" in ds.variables
                assert "init_atmosphere_qv" in ds.variables


class TestTranslationEngine:
    def test_produces_all_files(self):
        scenario = make_valid_baseline()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = translate_scenario(scenario, Path(tmpdir))
            assert "namelist" in result
            assert "static_driver" in result
            assert "dynamic_driver" in result
            assert "case_name" in result
            assert result["namelist"].exists()
            assert result["static_driver"].exists()
            assert result["dynamic_driver"].exists()
