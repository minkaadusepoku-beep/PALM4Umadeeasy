"""Queue load test: verify claim correctness, priority, retry, and throughput.

Uses the same single-session pattern as test_queue.py. Tests interleaved
claiming to verify the optimistic locking logic without SQLite write
contention.
"""

from __future__ import annotations

import os
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from src.db.database import Base
from src.db.models import Job, JobStatus, JobType, Project, ProjectMember, ProjectRole, ScenarioRecord, User
from src.workers.queue import (
    claim_next_job,
    generate_worker_id,
    heartbeat,
    mark_completed,
    mark_failed,
    requeue_stale_jobs,
)


@pytest.fixture
def sync_engine():
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(sync_engine):
    S = sessionmaker(bind=sync_engine)
    s = S()
    yield s
    s.close()


@pytest.fixture
def seed(session: Session):
    user = User(email="load@test.com", hashed_password="x", is_admin=False)
    session.add(user)
    session.flush()
    proj = Project(name="Load", user_id=user.id)
    session.add(proj)
    session.flush()
    mem = ProjectMember(project_id=proj.id, user_id=user.id, role=ProjectRole.owner)
    session.add(mem)
    session.flush()
    sc = ScenarioRecord(project_id=proj.id, name="s1", scenario_type="baseline", scenario_json="{}")
    session.add(sc)
    session.commit()
    return {"user_id": user.id, "project_id": proj.id, "scenario_id": sc.id}


def _enqueue(session: Session, seed, n: int, priority: int = 0) -> list[int]:
    ids = []
    for _ in range(n):
        j = Job(
            user_id=seed["user_id"],
            project_id=seed["project_id"],
            job_type=JobType.single,
            baseline_scenario_id=seed["scenario_id"],
            status=JobStatus.queued,
            priority=priority,
        )
        session.add(j)
        session.flush()
        ids.append(j.id)
    session.commit()
    return ids


def test_no_duplicate_claims(session, seed):
    """Two alternating workers, 20 jobs. No job claimed twice."""
    N = 20
    _enqueue(session, seed, N)

    w1, w2 = generate_worker_id(), generate_worker_id()
    claimed: list[int] = []

    for _ in range(N):
        for wid in (w1, w2):
            job = claim_next_job(session, wid)
            if job:
                claimed.append(job.id)
                mark_completed(session, job.id, "{}", "/tmp")

    assert len(claimed) == N
    assert len(set(claimed)) == N, "Duplicate claim"


def test_no_lost_jobs(session, seed):
    N = 15
    _enqueue(session, seed, N)

    wid = generate_worker_id()
    processed = 0
    while True:
        job = claim_next_job(session, wid)
        if not job:
            break
        mark_completed(session, job.id, '{"ok":true}', "/tmp")
        processed += 1

    assert processed == N
    assert session.query(Job).filter(Job.status == JobStatus.queued).count() == 0
    assert session.query(Job).filter(Job.status == JobStatus.running).count() == 0
    assert session.query(Job).filter(Job.status == JobStatus.completed).count() == N


def test_priority_ordering(session, seed):
    for prio in [0, 5, 2, 10, 1]:
        j = Job(
            user_id=seed["user_id"],
            project_id=seed["project_id"],
            job_type=JobType.single,
            baseline_scenario_id=seed["scenario_id"],
            status=JobStatus.queued,
            priority=prio,
        )
        session.add(j)
    session.commit()

    claimed_prio = []
    wid = generate_worker_id()
    for _ in range(5):
        job = claim_next_job(session, wid)
        assert job is not None
        claimed_prio.append(job.priority)
        mark_completed(session, job.id, "{}", "/tmp")

    assert claimed_prio == sorted(claimed_prio, reverse=True)


def test_retry_then_terminal_fail(session, seed):
    j = Job(
        user_id=seed["user_id"],
        project_id=seed["project_id"],
        job_type=JobType.single,
        baseline_scenario_id=seed["scenario_id"],
        status=JobStatus.queued,
        max_retries=2,
    )
    session.add(j)
    session.flush()
    jid = j.id
    session.commit()

    wid = generate_worker_id()
    for attempt in range(3):
        claimed = claim_next_job(session, wid)
        assert claimed is not None, f"Nothing to claim on attempt {attempt}"
        assert claimed.id == jid
        mark_failed(session, claimed.id, f"err-{attempt}")

    final = session.query(Job).get(jid)
    assert final.status == JobStatus.failed
    assert final.retry_count == 2


def test_heartbeat_and_stale_detection(session, seed):
    _enqueue(session, seed, 1)

    wid = generate_worker_id()
    job = claim_next_job(session, wid)
    assert job is not None

    assert heartbeat(session, job.id, wid) is True
    assert heartbeat(session, job.id, "wrong-worker") is False

    # Force stale
    from datetime import datetime, timezone
    from sqlalchemy import update as sa_update
    session.execute(
        sa_update(Job).where(Job.id == job.id).values(
            last_heartbeat=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
    )
    session.commit()

    recovered = requeue_stale_jobs(session, timeout_seconds=1)
    assert recovered == 1
    session.expire_all()
    refreshed = session.query(Job).get(job.id)
    assert refreshed.status == JobStatus.queued


def test_throughput_benchmark(session, seed):
    """Measure claim+complete rate. Reports throughput, not pass/fail."""
    N = 50
    _enqueue(session, seed, N)

    wid = generate_worker_id()
    start = time.monotonic()
    count = 0
    while True:
        job = claim_next_job(session, wid)
        if not job:
            break
        mark_completed(session, job.id, "{}", "/tmp")
        count += 1

    elapsed = time.monotonic() - start
    rate = count / elapsed if elapsed > 0 else 0
    print(f"\nQueue throughput: {count} jobs in {elapsed:.2f}s = {rate:.1f} jobs/s")
    assert count == N
