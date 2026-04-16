"""
Linux PALM worker — FastAPI service (Phase A skeleton).

See ADR-005 for the protocol and `linux_worker/README.md` for configuration.
Phase A uses a stub runner so the wire protocol can be exercised end-to-end
without a compiled PALM. Phase B swaps the stub for a real `mpirun palm`
call once PALM is available on the host.
"""

from __future__ import annotations

import io
import shutil
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from . import config
from .runner import RunnerError, execute_palm


# ---------------------------------------------------------------------------
# In-process job registry. Intentionally simple: one worker process, jobs
# serialised via a lock. Phase C can replace this with a real queue if we
# need concurrency.
# ---------------------------------------------------------------------------


@dataclass
class JobRecord:
    run_id: str
    case_name: str
    job_dir: Path
    status: str = "queued"  # queued | running | completed | failed
    message: str = ""
    wall_time_s: Optional[float] = None
    started_at: Optional[float] = None
    output_archive: Optional[Path] = None
    palm_version: str = config.PALM_VERSION_LABEL
    palm_build_flags: str = config.PALM_BUILD_FLAGS
    lock: threading.Lock = field(default_factory=threading.Lock)


_JOBS: dict[str, JobRecord] = {}
_JOBS_LOCK = threading.Lock()


def _register(job: JobRecord) -> None:
    with _JOBS_LOCK:
        _JOBS[job.run_id] = job


def _get(run_id: str) -> JobRecord:
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")
    return job


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def require_token(authorization: str = Header(default="")) -> None:
    if not config.PALM_WORKER_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="PALM_WORKER_TOKEN not configured on the worker",
        )
    expected = f"Bearer {config.PALM_WORKER_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(title="PALM4Umadeeasy Linux Worker", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "palm_version": config.PALM_VERSION_LABEL,
        "mode": config.PALM_WORKER_MODE,
    }


@app.post("/runs", dependencies=[Depends(require_token)])
async def submit_run(
    background: BackgroundTasks,
    case_name: str = Form(...),
    bundle: UploadFile = File(...),
) -> dict:
    run_id = uuid.uuid4().hex
    job_dir = config.PALM_WORKER_JOBDIR / run_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persist and unpack the uploaded bundle.
    raw_bundle_path = job_dir / "inputs.tar.gz"
    with open(raw_bundle_path, "wb") as fh:
        shutil.copyfileobj(bundle.file, fh)
    try:
        _safe_extract(raw_bundle_path, input_dir)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid input bundle: {exc}"
        ) from exc

    job = JobRecord(run_id=run_id, case_name=case_name, job_dir=job_dir)
    _register(job)

    background.add_task(_run_job, job, input_dir, output_dir)
    return {"run_id": run_id, "status": "queued"}


@app.get("/runs/{run_id}", dependencies=[Depends(require_token)])
def get_run(run_id: str) -> dict:
    job = _get(run_id)
    return {
        "run_id": job.run_id,
        "case_name": job.case_name,
        "status": job.status,
        "message": job.message,
        "wall_time_s": job.wall_time_s,
        "palm_version": job.palm_version,
        "palm_build_flags": job.palm_build_flags,
    }


@app.get("/runs/{run_id}/output", dependencies=[Depends(require_token)])
def get_output(run_id: str) -> StreamingResponse:
    job = _get(run_id)
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id} is not completed (status={job.status})",
        )
    if not job.output_archive or not job.output_archive.exists():
        raise HTTPException(status_code=410, detail="Output archive no longer available")

    def _iter():
        with open(job.output_archive, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    return
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{job.case_name}_output.tar.gz"'
        },
    )


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------


def _run_job(job: JobRecord, input_dir: Path, output_dir: Path) -> None:
    with job.lock:
        job.status = "running"
        job.started_at = time.monotonic()
    try:
        execute_palm(
            case_name=job.case_name,
            input_dir=input_dir,
            output_dir=output_dir,
            mode=config.PALM_WORKER_MODE,
            palm_binary=config.PALM_BINARY,
            mpi_np=config.PALM_MPI_NP,
        )
        archive = job.job_dir / "outputs.tar.gz"
        _pack_outputs(output_dir, archive)
        with job.lock:
            job.output_archive = archive
            job.wall_time_s = time.monotonic() - (job.started_at or time.monotonic())
            job.status = "completed"
            job.message = "ok"
    except RunnerError as exc:
        with job.lock:
            job.status = "failed"
            job.message = str(exc)
            job.wall_time_s = time.monotonic() - (job.started_at or time.monotonic())
    except Exception as exc:  # pragma: no cover — defensive
        with job.lock:
            job.status = "failed"
            job.message = f"Unexpected worker error: {exc}"
            job.wall_time_s = time.monotonic() - (job.started_at or time.monotonic())


# ---------------------------------------------------------------------------
# Tar helpers
# ---------------------------------------------------------------------------


def _safe_extract(archive: Path, dest: Path) -> None:
    """Extract ``archive`` into ``dest``, refusing path-traversal entries."""
    dest_resolved = dest.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(dest_resolved)):
                raise ValueError(f"Unsafe tar member path: {member.name}")
        tar.extractall(dest)


def _pack_outputs(output_dir: Path, archive: Path) -> None:
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(output_dir.iterdir()):
            tar.add(str(path), arcname=path.name)


# Expose the JobRecord-keyed registry for tests.
def _reset_for_tests() -> None:  # pragma: no cover — test hook
    with _JOBS_LOCK:
        _JOBS.clear()
