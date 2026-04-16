"""Health check logic for platform observability."""

import shutil
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import PALM_VERSION
from ..db.models import Job, JobStatus
from ..execution.settings import load_config


async def check_db(db: AsyncSession) -> dict:
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_queue(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    )
    counts = {row[0].value: row[1] for row in result.all()}

    # Check for stale workers (running jobs with old heartbeat)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
    stale_result = await db.execute(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.running,
            Job.last_heartbeat < cutoff,
        )
    )
    stale_count = stale_result.scalar() or 0

    return {
        "status": "healthy" if stale_count == 0 else "degraded",
        "jobs": {
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
        },
        "stale_workers": stale_count,
    }


def check_disk() -> dict:
    try:
        usage = shutil.disk_usage(".")
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
        pct_free = round(usage.free / usage.total * 100, 1)
        status = "healthy" if pct_free > 5 else ("degraded" if pct_free > 1 else "unhealthy")
        return {
            "status": status,
            "free_gb": free_gb,
            "total_gb": total_gb,
            "pct_free": pct_free,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_palm_runner(db: AsyncSession) -> dict:
    """
    Report the PALM execution backend (ADR-005).

    Reads the merged config (DB row if present, else env vars) so the UI
    shows exactly what ``run_palm()`` will use. ``*_source`` fields tell
    the operator whether each value came from the admin panel (``db``)
    or the environment.

    Status semantics:
      healthy  — the mode is configured well enough to dispatch a run.
      degraded — mode is set but prerequisites are missing (e.g. remote
                 without URL/token). The app still starts; runs will
                 fail loudly when submitted.
    """
    resolved = await load_config(db)
    mode = resolved.mode

    info: dict = {
        "mode": mode,
        "palm_version": PALM_VERSION,
        "mode_source": resolved.mode_source,
        "remote_url": resolved.remote_url or None,
        "remote_url_source": resolved.remote_url_source,
        "token_configured": resolved.token_configured,
        "remote_token_source": resolved.remote_token_source,
    }

    if mode == "stub":
        info["status"] = "healthy"
        info["note"] = "synthetic output; not a real PALM simulation"
        return info
    if mode == "remote":
        if not resolved.remote_url or not resolved.remote_token:
            info["status"] = "degraded"
            info["error"] = (
                "remote mode requires a worker URL and bearer token "
                "(set via /admin or PALM_REMOTE_URL / PALM_REMOTE_TOKEN)"
            )
        else:
            info["status"] = "healthy"
        return info
    if mode == "local":
        info["status"] = "healthy"
        info["note"] = "in-process mpirun (Linux only)"
        return info

    info["status"] = "degraded"
    info["error"] = f"unknown runner mode: {mode!r}"
    return info


async def get_health(db: AsyncSession) -> dict:
    db_health = await check_db(db)
    queue_health = await check_queue(db)
    disk_health = check_disk()
    palm_runner_health = await check_palm_runner(db)

    components = {
        "database": db_health,
        "queue": queue_health,
        "disk": disk_health,
        "palm_runner": palm_runner_health,
    }

    statuses = [c["status"] for c in components.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
