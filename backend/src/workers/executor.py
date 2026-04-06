"""Job executor — bridges the FastAPI app with the worker queue.

In development, starts an embedded worker thread so jobs execute automatically.
In production, jobs sit in the DB queue until an external worker picks them up.
"""

import logging
import os
import threading

from .worker import Worker

logger = logging.getLogger(__name__)

SYNC_DATABASE_URL = os.getenv("DATABASE_URL_SYNC", "sqlite:///./palm4u.db")

_embedded_worker: Worker | None = None
_embedded_worker_lock = threading.Lock()


def ensure_embedded_worker(db_url: str | None = None) -> None:
    """Start an embedded worker thread if not already running.

    Called once on API startup in dev mode.
    """
    global _embedded_worker
    with _embedded_worker_lock:
        if _embedded_worker is not None:
            return

        url = db_url or SYNC_DATABASE_URL
        _embedded_worker = Worker(url)
        thread = threading.Thread(target=_embedded_worker.start, daemon=True, name="embedded-worker")
        thread.start()
        logger.info("Embedded worker started on %s", url)


def stop_embedded_worker() -> None:
    global _embedded_worker
    with _embedded_worker_lock:
        if _embedded_worker is not None:
            _embedded_worker.stop()
            _embedded_worker = None


def run_job_background(job_id: int, db_url: str | None = None) -> None:
    """Ensure the embedded worker is running so queued jobs get picked up.

    The job is already in 'queued' state in the DB. The worker will claim it.
    In production with external workers, this is a no-op.
    """
    if os.getenv("PALM4U_EXTERNAL_WORKERS"):
        return

    ensure_embedded_worker(db_url)


def get_job_progress(job_id: int) -> dict:
    """Get job progress from DB (replaces old in-memory dict).

    Returns a simple status dict for WebSocket consumers.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from ..db.models import Job

    engine = create_engine(SYNC_DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "unknown"}
        result: dict = {"status": job.status.value}
        if job.status.value == "running":
            result["progress"] = 50  # Simplified; real progress requires spine callbacks
        elif job.status.value == "completed":
            result["progress"] = 100
        elif job.status.value == "failed":
            result["error"] = job.error_message or "Unknown error"
        return result
    finally:
        session.close()
        engine.dispose()
