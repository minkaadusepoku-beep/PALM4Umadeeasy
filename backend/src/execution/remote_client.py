"""
HTTP client for the remote Linux PALM worker (see ADR-005).

Wire format
-----------
- ``POST /runs`` — multipart upload of a tar.gz bundle containing the PALM
  inputs (``<case>_p3d``, ``<case>_static.nc``, ``<case>_dynamic.nc``).
  Response: ``{"run_id": "<uuid>", "status": "queued"}``.
- ``GET /runs/{run_id}`` — polling endpoint. Response includes ``status``
  (``queued``/``running``/``completed``/``failed``), optional ``message``,
  ``wall_time_s``, and reproducibility metadata (``palm_version``,
  ``palm_build_flags``).
- ``GET /runs/{run_id}/output`` — streaming download of a tar.gz containing
  everything the Linux worker wrote to the job's output directory. Only
  valid once ``status == "completed"``.

The client is deliberately synchronous: ``run_palm()`` is already called from
a worker thread and does not need another layer of async. Auth is a shared
bearer token (ADR-005 §Auth model v1).
"""

from __future__ import annotations

import io
import shutil
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from ..config import (
    PALM_REMOTE_POLL_INTERVAL_S,
    PALM_REMOTE_TIMEOUT_S,
)
from .runner import RunResult, RunStatus


class RemoteRunnerError(RuntimeError):
    """Raised when the remote worker reports failure or the transport errors out."""


# Terminal statuses reported by the Linux worker.
_TERMINAL_OK = {"completed"}
_TERMINAL_FAIL = {"failed", "cancelled", "timeout"}


@dataclass
class RemoteRunnerClient:
    """
    Thin HTTP client for ``linux_worker/``.

    Not thread-safe across concurrent runs on the same instance; callers
    should construct a new client per run (cheap) or per worker thread.
    """

    base_url: str
    token: str
    poll_interval_s: float = PALM_REMOTE_POLL_INTERVAL_S
    timeout_s: float = PALM_REMOTE_TIMEOUT_S
    # Per-request HTTP timeout; separate from the end-to-end ``timeout_s``
    # which governs how long we wait for the simulation to finish.
    http_timeout_s: float = 60.0

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    # -- public ------------------------------------------------------------

    def run(
        self,
        case_name: str,
        input_files: dict[str, Path],
        output_dir: Path,
    ) -> RunResult:
        """Submit a run, wait for completion, extract outputs into ``output_dir``."""
        started = time.monotonic()
        bundle = _pack_inputs(case_name, input_files)

        run_id = self._submit(case_name, bundle)
        final = self._poll_until_done(run_id)

        if final["status"] in _TERMINAL_FAIL:
            raise RemoteRunnerError(
                f"Remote worker reported {final['status']}: "
                f"{final.get('message', 'no message provided')}"
            )

        output_files = self._download_outputs(run_id, output_dir)
        wall = final.get("wall_time_s") or (time.monotonic() - started)

        return RunResult(
            status=RunStatus.COMPLETED,
            case_name=case_name,
            output_dir=output_dir,
            output_files=output_files,
            message=final.get("message", ""),
            wall_time_s=float(wall),
            palm_version=final.get("palm_version"),
            palm_build_flags=final.get("palm_build_flags"),
        )

    # -- internals ---------------------------------------------------------

    def _submit(self, case_name: str, bundle: bytes) -> str:
        files = {"bundle": (f"{case_name}.tar.gz", bundle, "application/gzip")}
        data = {"case_name": case_name}
        with httpx.Client(timeout=self.http_timeout_s) as client:
            resp = client.post(
                self._url("/runs"),
                headers=self._headers(),
                files=files,
                data=data,
            )
        if resp.status_code >= 400:
            raise RemoteRunnerError(
                f"POST /runs failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        payload = resp.json()
        run_id = payload.get("run_id")
        if not run_id:
            raise RemoteRunnerError(f"POST /runs returned no run_id: {payload!r}")
        return str(run_id)

    def _poll_until_done(self, run_id: str) -> dict:
        deadline = time.monotonic() + self.timeout_s
        with httpx.Client(timeout=self.http_timeout_s) as client:
            while True:
                resp = client.get(
                    self._url(f"/runs/{run_id}"),
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    raise RemoteRunnerError(
                        f"GET /runs/{run_id} failed: HTTP {resp.status_code} — "
                        f"{resp.text[:300]}"
                    )
                payload = resp.json()
                status = str(payload.get("status", "")).lower()
                if status in _TERMINAL_OK or status in _TERMINAL_FAIL:
                    return payload
                if time.monotonic() > deadline:
                    raise RemoteRunnerError(
                        f"Run {run_id} did not finish within "
                        f"{self.timeout_s:.0f}s (last status: {status!r})"
                    )
                time.sleep(self.poll_interval_s)

    def _download_outputs(self, run_id: str, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        url = self._url(f"/runs/{run_id}/output")
        buf = io.BytesIO()
        with httpx.Client(timeout=self.http_timeout_s) as client:
            with client.stream("GET", url, headers=self._headers()) as resp:
                if resp.status_code >= 400:
                    body = resp.read().decode(errors="replace")[:300]
                    raise RemoteRunnerError(
                        f"GET /runs/{run_id}/output failed: "
                        f"HTTP {resp.status_code} — {body}"
                    )
                for chunk in resp.iter_bytes():
                    buf.write(chunk)
        buf.seek(0)
        return _unpack_outputs(buf, output_dir)


# -- bundle helpers -------------------------------------------------------

# The bundle layout matches what the Linux worker expects (ADR-005 §File
# transfer format). Keys in ``input_files`` are the spine's convention;
# we rename into the PALM-native filenames on the way in.
_INPUT_KEY_TO_PALM_SUFFIX = {
    "namelist": "_p3d",
    "static_driver": "_static.nc",
    "dynamic_driver": "_dynamic.nc",
}


def _pack_inputs(case_name: str, input_files: dict[str, Path]) -> bytes:
    """Build a tar.gz bundle containing the PALM inputs."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for key, suffix in _INPUT_KEY_TO_PALM_SUFFIX.items():
            src = input_files.get(key)
            if src is None:
                # namelist/static are required; dynamic is optional.
                if key == "dynamic_driver":
                    continue
                raise RemoteRunnerError(
                    f"Missing required input '{key}' for remote PALM run"
                )
            src_path = Path(src)
            if not src_path.exists():
                raise RemoteRunnerError(f"Input file not found: {src_path}")
            arcname = f"{case_name}{suffix}"
            tar.add(str(src_path), arcname=arcname)
    return buf.getvalue()


def _unpack_outputs(buf: io.BytesIO, output_dir: Path) -> dict[str, Path]:
    """
    Extract the worker's output tar.gz into ``output_dir``.

    Returns a dict keyed by a short logical name the spine's post-processor
    understands (``av_3d``, ``ts``, etc.) pointing at the extracted file.
    Files we don't recognise are still extracted — the spine just ignores them.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, Path] = {}
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            # Guard against path-traversal from a hostile tar.
            safe_name = Path(member.name).name
            if not safe_name or safe_name.startswith((".", "/")):
                continue
            dest = output_dir / safe_name
            with tar.extractfile(member) as src, open(dest, "wb") as dst:
                if src is None:
                    continue
                shutil.copyfileobj(src, dst)
            key = _classify_output(safe_name)
            if key and key not in extracted:
                extracted[key] = dest
    return extracted


def _classify_output(filename: str) -> Optional[str]:
    """
    Map a PALM output filename to the short key the spine expects.

    Conservative: only recognises the files the post-processor actually
    consumes today. Unknown files are still written to disk by the caller
    but won't appear in the returned dict.
    """
    lower = filename.lower()
    if lower.endswith("_av_3d.nc") or "_av_3d." in lower:
        return "av_3d"
    if lower.endswith("_3d.nc") or lower.endswith("_xy.nc"):
        return "3d"
    if lower.endswith("_ts.nc"):
        return "ts"
    if lower.endswith("_masked.nc"):
        return "masked"
    return None
