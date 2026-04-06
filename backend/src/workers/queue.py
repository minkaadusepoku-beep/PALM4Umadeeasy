"""DB-backed job queue manager.

All queue operations use synchronous SQLAlchemy sessions because workers
run in separate threads/processes outside the async FastAPI event loop.
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..db.models import Job, JobStatus


def generate_worker_id() -> str:
    return f"worker-{uuid.uuid4().hex[:8]}"


def claim_next_job(session: Session, worker_id: str) -> Job | None:
    """Atomically claim the next queued job using optimistic locking.

    Returns the claimed Job or None if no jobs are available.
    """
    job = (
        session.query(Job)
        .filter(Job.status == JobStatus.queued)
        .order_by(Job.priority.desc(), Job.queued_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        return None

    # Atomic claim: only update if still queued
    rows = session.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == JobStatus.queued)
        .values(
            status=JobStatus.running,
            worker_id=worker_id,
            started_at=datetime.now(timezone.utc),
            last_heartbeat=datetime.now(timezone.utc),
        )
    )
    session.commit()

    if rows.rowcount == 0:
        # Another worker claimed it
        return None

    session.refresh(job)
    return job


def heartbeat(session: Session, job_id: int, worker_id: str) -> bool:
    """Update heartbeat timestamp. Returns False if job was reassigned."""
    rows = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.worker_id == worker_id, Job.status == JobStatus.running)
        .values(last_heartbeat=datetime.now(timezone.utc))
    )
    session.commit()
    return rows.rowcount > 0


def mark_completed(session: Session, job_id: int, result_json: str, output_dir: str) -> None:
    session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=JobStatus.completed,
            result_json=result_json,
            output_dir=output_dir,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def mark_failed(session: Session, job_id: int, error_message: str) -> None:
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        return

    if job.retry_count < job.max_retries:
        # Re-queue for retry
        session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.queued,
                worker_id=None,
                last_heartbeat=None,
                started_at=None,
                retry_count=job.retry_count + 1,
                error_message=error_message,
            )
        )
    else:
        session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.failed,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
        )
    session.commit()


def mark_cancelled(session: Session, job_id: int) -> bool:
    """Cancel a queued job. Returns True if successfully cancelled."""
    rows = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.queued)
        .values(
            status=JobStatus.cancelled,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    return rows.rowcount > 0


def requeue_job(session: Session, job_id: int) -> bool:
    """Re-queue a failed or cancelled job for retry. Returns True on success."""
    rows = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status.in_([JobStatus.failed, JobStatus.cancelled]),
        )
        .values(
            status=JobStatus.queued,
            worker_id=None,
            last_heartbeat=None,
            started_at=None,
            completed_at=None,
            error_message=None,
            retry_count=0,
        )
    )
    session.commit()
    return rows.rowcount > 0


def requeue_stale_jobs(session: Session, timeout_seconds: int = 120) -> int:
    """Find running jobs with expired heartbeats and re-queue or fail them.

    Returns the number of jobs affected.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    stale_jobs = (
        session.query(Job)
        .filter(
            Job.status == JobStatus.running,
            Job.last_heartbeat < cutoff,
        )
        .all()
    )

    count = 0
    for job in stale_jobs:
        if job.retry_count < job.max_retries:
            job.status = JobStatus.queued
            job.worker_id = None
            job.last_heartbeat = None
            job.started_at = None
            job.retry_count += 1
            job.error_message = f"Stale job detected (no heartbeat for {timeout_seconds}s)"
        else:
            job.status = JobStatus.failed
            job.error_message = f"Stale job failed after {job.max_retries} retries"
            job.completed_at = datetime.now(timezone.utc)
        count += 1

    if count:
        session.commit()
    return count


def recover_interrupted_jobs(session: Session) -> int:
    """On startup, re-queue any jobs stuck in 'running' state (server crashed).

    Returns the number of recovered jobs.
    """
    rows = session.execute(
        update(Job)
        .where(Job.status == JobStatus.running)
        .values(
            status=JobStatus.queued,
            worker_id=None,
            last_heartbeat=None,
            started_at=None,
        )
    )
    session.commit()
    return rows.rowcount
