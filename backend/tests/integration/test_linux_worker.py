"""
Integration test: Windows RemoteRunnerClient <-> real linux_worker FastAPI app.

The unit tests in test_execution_runner.py mock the transport. This one wires
the *actual* Linux worker (via FastAPI's TestClient, which handles the ASGI
lifespan and background tasks in-process) against the client's own
bundle-pack / output-classify code. Exercises the full wire protocol from
ADR-005 without needing a real Linux host or a real socket.

What this catches that the mocked tests cannot:
- Auth header contract drift between client and server
- Multipart form field name mismatch (``bundle`` vs something else)
- tar.gz round-trip compatibility between ``_pack_inputs`` and the worker's
  ``_safe_extract`` + stub runner + ``_pack_outputs`` + client's ``_unpack_outputs``
- FastAPI Pydantic response shape drift vs client's ``_poll_until_done`` keys
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import netCDF4 as nc
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# linux_worker lives at the project root, a sibling of backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.execution.remote_client import (  # noqa: E402
    _classify_output,
    _pack_inputs,
    _unpack_outputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def worker_app(tmp_path, monkeypatch):
    """Import the worker with a tmp job dir and a known bearer token."""
    monkeypatch.setenv("PALM_WORKER_TOKEN", "it-token")
    monkeypatch.setenv("PALM_WORKER_JOBDIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("PALM_WORKER_MODE", "stub")
    monkeypatch.setenv("PALM_VERSION_LABEL", "23.10-int-test")
    monkeypatch.setenv("PALM_BUILD_FLAGS", "-O3 -integration")

    # Force a fresh import so the env vars take effect.
    for mod in ("linux_worker.main", "linux_worker.runner", "linux_worker.config"):
        sys.modules.pop(mod, None)

    from linux_worker.main import app, _reset_for_tests  # noqa: WPS433

    _reset_for_tests()
    return app


@pytest.fixture
def client(worker_app):
    with TestClient(worker_app) as c:
        yield c


def _make_static_driver(path: Path, nx: int = 6, ny: int = 6) -> Path:
    with nc.Dataset(str(path), "w", format="NETCDF4") as ds:
        ds.createDimension("x", nx)
        ds.createDimension("y", ny)
        xv = ds.createVariable("x", "f4", ("x",))
        xv[:] = np.arange(nx, dtype=np.float32)
        yv = ds.createVariable("y", "f4", ("y",))
        yv[:] = np.arange(ny, dtype=np.float32)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_is_unauthenticated(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        # Surface the runner mode so ops can see what they're running.
        assert body["mode"] == "stub"
        assert body["palm_version"] == "23.10-int-test"


class TestAuth:
    def test_submit_rejects_missing_token(self, client, tmp_path):
        static = _make_static_driver(tmp_path / "case_static.nc")
        namelist = tmp_path / "case_p3d"
        namelist.write_text("&init\n/")
        bundle = _pack_inputs(
            "case", {"namelist": namelist, "static_driver": static}
        )
        resp = client.post(
            "/runs",
            data={"case_name": "case"},
            files={"bundle": ("case.tar.gz", bundle, "application/gzip")},
        )
        assert resp.status_code == 401

    def test_submit_rejects_wrong_token(self, client, tmp_path):
        static = _make_static_driver(tmp_path / "case_static.nc")
        namelist = tmp_path / "case_p3d"
        namelist.write_text("&init\n/")
        bundle = _pack_inputs(
            "case", {"namelist": namelist, "static_driver": static}
        )
        resp = client.post(
            "/runs",
            headers={"Authorization": "Bearer wrong"},
            data={"case_name": "case"},
            files={"bundle": ("case.tar.gz", bundle, "application/gzip")},
        )
        assert resp.status_code == 401


class TestRoundTrip:
    def test_submit_poll_download_end_to_end(self, client, tmp_path):
        """
        Full wire contract: pack on the Windows side, unpack on the Linux
        side, run the stub, pack outputs, ship back, unpack on the Windows
        side. Must round-trip the PALM filenames intact.
        """
        auth = {"Authorization": "Bearer it-token"}

        static_src = _make_static_driver(tmp_path / "case_static.nc")
        namelist_src = tmp_path / "case_p3d"
        namelist_src.write_text("&initialization_parameters\n/")

        bundle = _pack_inputs(
            "case",
            {"namelist": namelist_src, "static_driver": static_src},
        )

        # ---- POST /runs
        resp = client.post(
            "/runs",
            headers=auth,
            data={"case_name": "case"},
            files={"bundle": ("case.tar.gz", bundle, "application/gzip")},
        )
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["run_id"]
        assert run_id

        # ---- GET /runs/{id} — poll until completed (TestClient runs
        # BackgroundTasks synchronously after the response, so one poll
        # should already show completed).
        deadline = time.monotonic() + 5.0
        final = None
        while time.monotonic() < deadline:
            poll = client.get(f"/runs/{run_id}", headers=auth)
            assert poll.status_code == 200, poll.text
            payload = poll.json()
            if payload["status"] in ("completed", "failed"):
                final = payload
                break
            time.sleep(0.05)
        assert final is not None, "worker never reached a terminal state"
        assert final["status"] == "completed", final
        assert final["palm_version"] == "23.10-int-test"
        assert final["palm_build_flags"] == "-O3 -integration"
        assert final["wall_time_s"] is not None

        # ---- GET /runs/{id}/output
        out_resp = client.get(f"/runs/{run_id}/output", headers=auth)
        assert out_resp.status_code == 200
        assert out_resp.headers["content-type"].startswith("application/gzip")

        output_dir = tmp_path / "out"
        extracted = _unpack_outputs(io.BytesIO(out_resp.content), output_dir)
        # Stub writes <case>_av_3d.nc — the client must classify that under "av_3d".
        assert "av_3d" in extracted
        assert extracted["av_3d"].name == "case_av_3d.nc"
        assert extracted["av_3d"].exists()
        assert extracted["av_3d"].stat().st_size > 0
        # STUB_README carried across too but left unclassified.
        assert (output_dir / "STUB_README.txt").exists()

    def test_output_download_before_completion_rejected(self, client, tmp_path):
        """The worker must not hand out outputs mid-run. Belt-and-braces."""
        # We build a job record but swap the status to "running" before
        # attempting the download, to prove the state guard.
        import linux_worker.main as worker_main

        auth = {"Authorization": "Bearer it-token"}
        static = _make_static_driver(tmp_path / "case_static.nc")
        namelist = tmp_path / "case_p3d"
        namelist.write_text("&init\n/")
        bundle = _pack_inputs(
            "case", {"namelist": namelist, "static_driver": static}
        )
        resp = client.post(
            "/runs",
            headers=auth,
            data={"case_name": "case"},
            files={"bundle": ("case.tar.gz", bundle, "application/gzip")},
        )
        run_id = resp.json()["run_id"]

        # Force the job back to "running" — simulate in-flight state.
        job = worker_main._JOBS[run_id]
        job.status = "running"
        job.output_archive = None

        out = client.get(f"/runs/{run_id}/output", headers=auth)
        assert out.status_code == 409

    def test_unknown_run_id_returns_404(self, client):
        auth = {"Authorization": "Bearer it-token"}
        assert client.get("/runs/does-not-exist", headers=auth).status_code == 404
        assert (
            client.get("/runs/does-not-exist/output", headers=auth).status_code == 404
        )


class TestOutputClassification:
    """Defensive: the classifier is the contract between the worker's
    filenames and the post-processor's expected keys. Pin it here so a
    rename on either side fails loudly."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("case_av_3d.nc", "av_3d"),
            ("CASE_AV_3D.NC", "av_3d"),
            ("scenario_3d.nc", "3d"),
            ("case_xy.nc", "3d"),
            ("case_ts.nc", "ts"),
            ("case_masked.nc", "masked"),
            ("RUN_case.log", None),
            ("STUB_README.txt", None),
        ],
    )
    def test_known_filenames(self, filename, expected):
        assert _classify_output(filename) == expected
