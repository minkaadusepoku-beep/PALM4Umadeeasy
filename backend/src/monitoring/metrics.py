"""Prometheus-compatible metrics collection."""

import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Job, JobStatus, User, Project


async def collect_metrics(db: AsyncSession) -> str:
    """Generate Prometheus text-format metrics."""
    lines: list[str] = []

    # Job counts by status
    result = await db.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    )
    lines.append("# HELP palm4u_jobs_total Total number of jobs by status")
    lines.append("# TYPE palm4u_jobs_total gauge")
    for status, count in result.all():
        lines.append(f'palm4u_jobs_total{{status="{status.value}"}} {count}')

    # Active workers (distinct worker_ids on running jobs)
    result = await db.execute(
        select(func.count(func.distinct(Job.worker_id))).where(
            Job.status == JobStatus.running,
            Job.worker_id.isnot(None),
        )
    )
    active_workers = result.scalar() or 0
    lines.append("# HELP palm4u_active_workers Number of active workers")
    lines.append("# TYPE palm4u_active_workers gauge")
    lines.append(f"palm4u_active_workers {active_workers}")

    # Queue depth
    result = await db.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.queued)
    )
    queue_depth = result.scalar() or 0
    lines.append("# HELP palm4u_queue_depth Number of jobs waiting in queue")
    lines.append("# TYPE palm4u_queue_depth gauge")
    lines.append(f"palm4u_queue_depth {queue_depth}")

    # User count
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar() or 0
    lines.append("# HELP palm4u_users_total Total registered users")
    lines.append("# TYPE palm4u_users_total gauge")
    lines.append(f"palm4u_users_total {user_count}")

    # Project count
    result = await db.execute(select(func.count(Project.id)))
    project_count = result.scalar() or 0
    lines.append("# HELP palm4u_projects_total Total projects")
    lines.append("# TYPE palm4u_projects_total gauge")
    lines.append(f"palm4u_projects_total {project_count}")

    # Uptime
    lines.append("# HELP palm4u_info Platform info")
    lines.append("# TYPE palm4u_info gauge")
    lines.append(f'palm4u_info{{version="0.1.0"}} 1')

    return "\n".join(lines) + "\n"
