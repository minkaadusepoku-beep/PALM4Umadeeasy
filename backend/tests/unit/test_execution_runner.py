"""
Unit tests for the runner mode dispatcher and the remote HTTP client.

Covers:
- Mode resolution precedence (explicit arg > stub flag > env default)
- Stub branch still works (backward compatibility)
- Remote branch raises cleanly when not configured
- Local branch raises NotImplementedError until Phase B
- RemoteRunnerClient packs inputs, polls, and unpacks outputs over a mocked
  httpx transport.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.execution import runner as runner_mod
from src.execution import settings as settings_mod
from src.execution.settings import ResolvedRunnerConfig
from src.execution.runner import (
    RunnerMode,
    RunResult,
    RunStatus,
    _resolve_mode,
    run_palm,
)


def _patch_resolved(monkeypatch, *, mode: str, remote_url: str = "", remote_token: str = ""):
    """Force settings.load_config_sync() to return a known config for tests."""
    def _fake() -> ResolvedRunnerConfig:
        return ResolvedRunnerConfig(
            mode=mode,
            remote_url=remote_url,
            remote_token=remote_token,
            mode_source="env",
            remote_url_source="env" if remote_url else "unset",
            remote_token_source="env" if remote_token else "unset",
        )
    monkeypatch.setattr(settings_mod, "load_config_sync", _fake)


# ---------------------------------------------------------------------------
# _resolve_mode precedence
# ---------------------------------------------------------------------------


class TestResolveMode:
    def test_explicit_mode_wins_over_stub_flag(self):
        assert _resolve_mode(stub=True, mode="remote") == RunnerMode.REMOTE
        assert _resolve_mode(stub=False, mode="stub") == RunnerMode.STUB

    def test_stub_true_forces_stub(self):
        assert _resolve_mode(stub=True, mode=None) == RunnerMode.STUB

    def test_stub_false_defers_to_config_but_never_stays_stub(self, monkeypatch):
        # If resolved config says "stub" but caller explicitly passed stub=False,
        # we must not silently keep running in stub — fall back to local instead.
        _patch_resolved(monkeypatch, mode="stub")
        assert _resolve_mode(stub=False, mode=None) == RunnerMode.LOCAL

    def test_stub_false_respects_non_stub_config(self, monkeypatch):
        _patch_resolved(monkeypatch, mode="remote", remote_url="x", remote_token="t")
        assert _resolve_mode(stub=False, mode=None) == RunnerMode.REMOTE

    def test_defaults_to_resolved_config(self, monkeypatch):
        _patch_resolved(monkeypatch, mode="remote", remote_url="x", remote_token="t")
        assert _resolve_mode(stub=None, mode=None) == RunnerMode.REMOTE

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            _resolve_mode(stub=None, mode="quantum")


# ---------------------------------------------------------------------------
# run_palm() dispatch
# ---------------------------------------------------------------------------


def _make_static_driver(tmp_path: Path, nx: int = 4, ny: int = 4) -> Path:
    """Minimal NetCDF static driver for the stub runner."""
    import netCDF4 as nc
    import numpy as np

    path = tmp_path / "case_static.nc"
    with nc.Dataset(str(path), "w", format="NETCDF4") as ds:
        ds.createDimension("x", nx)
        ds.createDimension("y", ny)
        xv = ds.createVariable("x", "f4", ("x",))
        xv[:] = np.arange(nx, dtype=np.float32)
        yv = ds.createVariable("y", "f4", ("y",))
        yv[:] = np.arange(ny, dtype=np.float32)
    return path


class TestRunPalmDispatch:
    def test_stub_mode_produces_output(self, tmp_path):
        static = _make_static_driver(tmp_path)
        out = tmp_path / "output"
        result = run_palm(
            case_name="case",
            input_files={"static_driver": static},
            output_dir=out,
            stub=True,
            seed=42,
        )
        assert result.status == RunStatus.STUBBED
        assert "av_3d" in result.output_files
        assert result.output_files["av_3d"].exists()

    def test_local_mode_not_implemented(self, tmp_path):
        static = _make_static_driver(tmp_path)
        with pytest.raises(NotImplementedError):
            run_palm(
                case_name="case",
                input_files={"static_driver": static},
                output_dir=tmp_path / "out",
                mode="local",
            )

    def test_remote_mode_without_url_fails_loudly(self, tmp_path, monkeypatch):
        _patch_resolved(monkeypatch, mode="remote", remote_url="", remote_token="tok")
        static = _make_static_driver(tmp_path)
        with pytest.raises(RuntimeError, match="worker URL"):
            run_palm(
                case_name="case",
                input_files={"static_driver": static},
                output_dir=tmp_path / "out",
                mode="remote",
            )

    def test_remote_mode_without_token_fails_loudly(self, tmp_path, monkeypatch):
        _patch_resolved(
            monkeypatch, mode="remote", remote_url="http://worker:8765", remote_token=""
        )
        static = _make_static_driver(tmp_path)
        with pytest.raises(RuntimeError, match="bearer token"):
            run_palm(
                case_name="case",
                input_files={"static_driver": static},
                output_dir=tmp_path / "out",
                mode="remote",
            )


# ---------------------------------------------------------------------------
# RemoteRunnerClient end-to-end against a mocked transport
# ---------------------------------------------------------------------------


def _tar_gz_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _MockWorker:
    """
    In-memory substitute for the Linux worker. Implements the three-endpoint
    protocol from ADR-005 just well enough to drive RemoteRunnerClient.
    """

    def __init__(self, output_files: dict[str, bytes]):
        self.output_files = output_files
        self.received_bundle: bytes | None = None
        self.received_case: str | None = None
        self.poll_count = 0
        # Return "running" once, then "completed". Covers the happy-path
        # polling loop without slowing the test.
        self.statuses = ["running", "completed"]

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and url.endswith("/runs"):
            # Parse multipart to grab case_name + bundle
            self.received_bundle = request.content
            self.received_case = "echoed"
            return httpx.Response(
                200, json={"run_id": "test-run-1", "status": "queued"}
            )
        if request.method == "GET" and "/runs/test-run-1/output" in url:
            body = _tar_gz_bytes(self.output_files)
            return httpx.Response(
                200,
                content=body,
                headers={"content-type": "application/gzip"},
            )
        if request.method == "GET" and "/runs/test-run-1" in url:
            status = self.statuses[min(self.poll_count, len(self.statuses) - 1)]
            self.poll_count += 1
            return httpx.Response(
                200,
                json={
                    "run_id": "test-run-1",
                    "status": status,
                    "message": "ok" if status == "completed" else "",
                    "wall_time_s": 12.5 if status == "completed" else None,
                    "palm_version": "23.10",
                    "palm_build_flags": "-O3 -march=native",
                },
            )
        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {url}"})


@pytest.fixture
def mock_transport_factory():
    """Returns a helper that patches httpx.Client to use a MockTransport."""
    from unittest.mock import patch

    def _install(worker: _MockWorker):
        transport = httpx.MockTransport(worker.handle)
        real_init = httpx.Client.__init__

        def fake_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            real_init(self, *args, **kwargs)

        return patch.object(httpx.Client, "__init__", fake_init)

    return _install


class TestRemoteRunnerClient:
    def test_happy_path_packs_submits_polls_and_unpacks(
        self, tmp_path, mock_transport_factory
    ):
        from src.execution.remote_client import RemoteRunnerClient

        # Create a fake static driver to hand to the client.
        static = _make_static_driver(tmp_path)
        namelist = tmp_path / "case_p3d"
        namelist.write_text("&initialization_parameters\n/")

        output_dir = tmp_path / "output"

        # The "worker" will return this as its output bundle.
        worker = _MockWorker(
            output_files={
                "case_av_3d.nc": b"fake netcdf bytes",
                "RUN_case.log": b"dummy log",
            }
        )

        with mock_transport_factory(worker):
            client = RemoteRunnerClient(
                base_url="http://worker:8765",
                token="test-token",
                poll_interval_s=0.0,  # don't wait between polls in tests
                timeout_s=10.0,
            )
            result = client.run(
                case_name="case",
                input_files={
                    "namelist": namelist,
                    "static_driver": static,
                },
                output_dir=output_dir,
            )

        assert isinstance(result, RunResult)
        assert result.status == RunStatus.COMPLETED
        assert result.palm_version == "23.10"
        assert result.palm_build_flags == "-O3 -march=native"
        assert result.wall_time_s == 12.5
        # av_3d key must be wired through so the post-processor can find it.
        assert "av_3d" in result.output_files
        assert result.output_files["av_3d"].read_bytes() == b"fake netcdf bytes"
        # Unrecognised outputs are still extracted, just not classified.
        assert (output_dir / "RUN_case.log").exists()
        # Polled at least twice (running → completed).
        assert worker.poll_count >= 2

    def test_reports_worker_failure(self, tmp_path, mock_transport_factory):
        from src.execution.remote_client import (
            RemoteRunnerClient,
            RemoteRunnerError,
        )

        static = _make_static_driver(tmp_path)
        namelist = tmp_path / "case_p3d"
        namelist.write_text("&init\n/")

        worker = _MockWorker(output_files={})
        worker.statuses = ["failed"]  # immediate failure

        with mock_transport_factory(worker):
            client = RemoteRunnerClient(
                base_url="http://worker:8765",
                token="test-token",
                poll_interval_s=0.0,
                timeout_s=5.0,
            )
            with pytest.raises(RemoteRunnerError, match="failed"):
                client.run(
                    case_name="case",
                    input_files={"namelist": namelist, "static_driver": static},
                    output_dir=tmp_path / "out",
                )

    def test_missing_required_input_rejected_before_network(self, tmp_path):
        """We must not upload partial bundles — reject missing namelist locally."""
        from src.execution.remote_client import (
            RemoteRunnerClient,
            RemoteRunnerError,
        )

        static = _make_static_driver(tmp_path)
        client = RemoteRunnerClient(
            base_url="http://worker:8765",
            token="test-token",
        )
        with pytest.raises(RemoteRunnerError, match="namelist"):
            client.run(
                case_name="case",
                input_files={"static_driver": static},  # no namelist
                output_dir=tmp_path / "out",
            )

    def test_bundle_contains_expected_palm_filenames(self, tmp_path):
        """The bundle must use PALM's native filenames, not our internal keys."""
        from src.execution.remote_client import _pack_inputs

        namelist = tmp_path / "scratch_p3d"
        namelist.write_text("&init\n/")
        static = _make_static_driver(tmp_path)
        dynamic = tmp_path / "case_dynamic.nc"
        dynamic.write_bytes(b"dummy")

        data = _pack_inputs(
            "case",
            {
                "namelist": namelist,
                "static_driver": static,
                "dynamic_driver": dynamic,
            },
        )
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            names = sorted(m.name for m in tar.getmembers())
        assert names == ["case_dynamic.nc", "case_p3d", "case_static.nc"]

    def test_unpack_rejects_path_traversal(self, tmp_path):
        """A malicious worker must not be able to write outside output_dir."""
        from src.execution.remote_client import _unpack_outputs

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="../../../etc/passwd")
            payload = b"bad"
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        buf.seek(0)

        out = tmp_path / "out"
        extracted = _unpack_outputs(buf, out)
        # Traversal entry was skipped (no files classified, none written above
        # out/). We only assert nothing escaped out/.
        escaped = list(tmp_path.parent.glob("etc/passwd"))
        assert escaped == []
        # output dir itself is fine (empty or only safe entries).
        for p in out.rglob("*"):
            assert str(p.resolve()).startswith(str(out.resolve()))
