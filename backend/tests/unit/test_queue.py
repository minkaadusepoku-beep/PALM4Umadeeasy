"""Unit tests for the DB-backed job queue system."""

import os
import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Override DB URL before importing models
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from src.db.database import Base
from src.db.models import Job, JobStatus, JobType, User, Project, ScenarioRecord, ProjectMember, ProjectRole
from src.workers.queue import (
    claim_next_job,
    generate_worker_id,
    heartbeat,
    mark_completed,
    mark_failed,
    mark_cancelled,
    requeue_job,
    requeue_stale_jobs,
    recover_interrupted_jobs,
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
    SessionLocal = sessionmaker(bind=sync_engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def setup_data(session: Session):
    """Create a user, project, scenario, and return their IDs."""
    user = User(email="test@test.com", hashed_password="hashed")
    session.add(user)
    session.flush()

    project = Project(name="Test Project", user_id=user.id)
    session.add(project)
    session.flush()

    membership = ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.owner)
    session.add(membership)
    session.flush()

    scenario = ScenarioRecord(
        project_id=project.id,
        name="Test Scenario",
        scenario_type="single",
        scenario_json='{"name": "test", "scenario_type": "single", "domain": {"bbox": {"west": 356000, "south": 5645000, "east": 356500, "north": 5645500}, "epsg": 25832, "dx": 10, "dz": 10, "nz": 20}, "vegetation": {"mode": "uniform_grass"}, "forcing": {"mode": "default_summer"}, "simulation": {"duration_hours": 1, "output_interval_minutes": 30}}',
    )
    session.add(scenario)
    session.commit()

    return {"user_id": user.id, "project_id": project.id, "scenario_id": scenario.id}


def _create_job(session: Session, data: dict, status=JobStatus.queued, priority=0) -> Job:
    job = Job(
        user_id=data["user_id"],
        project_id=data["project_id"],
        job_type=JobType.single,
        baseline_scenario_id=data["scenario_id"],
        status=status,
        priority=priority,
    )
    session.add(job)
    session.commit()
    return job


class TestClaimJob:
    def test_claim_next_job(self, session, setup_data):
        job = _create_job(session, setup_data)
        worker_id = generate_worker_id()

        claimed = claim_next_job(session, worker_id)

        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == JobStatus.running
        assert claimed.worker_id == worker_id
        assert claimed.started_at is not None
        assert claimed.last_heartbeat is not None

    def test_claim_returns_none_when_empty(self, session, setup_data):
        claimed = claim_next_job(session, "worker-1")
        assert claimed is None

    def test_claim_respects_priority(self, session, setup_data):
        low = _create_job(session, setup_data, priority=0)
        high = _create_job(session, setup_data, priority=10)

        claimed = claim_next_job(session, "worker-1")
        assert claimed.id == high.id

    def test_claim_respects_fifo_within_priority(self, session, setup_data):
        first = _create_job(session, setup_data)
        second = _create_job(session, setup_data)

        claimed = claim_next_job(session, "worker-1")
        assert claimed.id == first.id

    def test_claim_skips_non_queued(self, session, setup_data):
        running = _create_job(session, setup_data, status=JobStatus.running)
        queued = _create_job(session, setup_data)

        claimed = claim_next_job(session, "worker-1")
        assert claimed.id == queued.id


class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self, session, setup_data):
        job = _create_job(session, setup_data)
        worker_id = "worker-1"
        claimed = claim_next_job(session, worker_id)

        old_hb = claimed.last_heartbeat
        ok = heartbeat(session, claimed.id, worker_id)
        assert ok is True

        session.refresh(claimed)
        assert claimed.last_heartbeat >= old_hb

    def test_heartbeat_rejects_wrong_worker(self, session, setup_data):
        job = _create_job(session, setup_data)
        claim_next_job(session, "worker-1")

        ok = heartbeat(session, job.id, "worker-2")
        assert ok is False


class TestMarkCompleted:
    def test_mark_completed(self, session, setup_data):
        job = _create_job(session, setup_data)
        claim_next_job(session, "worker-1")

        mark_completed(session, job.id, '{"result": "ok"}', "/tmp/output")

        session.refresh(job)
        assert job.status == JobStatus.completed
        assert job.result_json == '{"result": "ok"}'
        assert job.output_dir == "/tmp/output"
        assert job.completed_at is not None


class TestMarkFailed:
    def test_mark_failed_with_retries(self, session, setup_data):
        job = _create_job(session, setup_data)
        job.max_retries = 3
        session.commit()
        claim_next_job(session, "worker-1")

        mark_failed(session, job.id, "some error")

        session.refresh(job)
        assert job.status == JobStatus.queued
        assert job.retry_count == 1
        assert job.worker_id is None

    def test_mark_failed_exhausted_retries(self, session, setup_data):
        job = _create_job(session, setup_data)
        job.max_retries = 0
        session.commit()
        claim_next_job(session, "worker-1")

        mark_failed(session, job.id, "final error")

        session.refresh(job)
        assert job.status == JobStatus.failed
        assert job.completed_at is not None


class TestCancel:
    def test_cancel_queued_job(self, session, setup_data):
        job = _create_job(session, setup_data)

        result = mark_cancelled(session, job.id)

        assert result is True
        session.refresh(job)
        assert job.status == JobStatus.cancelled

    def test_cancel_non_queued_fails(self, session, setup_data):
        job = _create_job(session, setup_data, status=JobStatus.running)

        result = mark_cancelled(session, job.id)

        assert result is False


class TestRequeue:
    def test_requeue_failed_job(self, session, setup_data):
        job = _create_job(session, setup_data, status=JobStatus.failed)

        result = requeue_job(session, job.id)

        assert result is True
        session.refresh(job)
        assert job.status == JobStatus.queued
        assert job.retry_count == 0

    def test_requeue_cancelled_job(self, session, setup_data):
        job = _create_job(session, setup_data, status=JobStatus.cancelled)

        result = requeue_job(session, job.id)

        assert result is True
        session.refresh(job)
        assert job.status == JobStatus.queued

    def test_requeue_running_job_fails(self, session, setup_data):
        job = _create_job(session, setup_data, status=JobStatus.running)

        result = requeue_job(session, job.id)

        assert result is False


class TestStaleDetection:
    def test_requeue_stale_jobs(self, session, setup_data):
        job = _create_job(session, setup_data)
        claim_next_job(session, "worker-1")

        # Manually set heartbeat to past
        job.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=300)
        session.commit()

        count = requeue_stale_jobs(session, timeout_seconds=60)

        assert count == 1
        session.refresh(job)
        assert job.status == JobStatus.queued
        assert job.retry_count == 1

    def test_stale_job_exhausted_retries(self, session, setup_data):
        job = _create_job(session, setup_data)
        job.max_retries = 0
        session.commit()
        claim_next_job(session, "worker-1")

        job.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=300)
        session.commit()

        count = requeue_stale_jobs(session, timeout_seconds=60)

        assert count == 1
        session.refresh(job)
        assert job.status == JobStatus.failed

    def test_healthy_jobs_not_affected(self, session, setup_data):
        job = _create_job(session, setup_data)
        claim_next_job(session, "worker-1")
        # Heartbeat is fresh (just set by claim)

        count = requeue_stale_jobs(session, timeout_seconds=60)

        assert count == 0
        session.refresh(job)
        assert job.status == JobStatus.running


class TestRecoverInterrupted:
    def test_recover_running_jobs_on_startup(self, session, setup_data):
        job1 = _create_job(session, setup_data)
        claim_next_job(session, "worker-1")

        job2 = _create_job(session, setup_data)  # stays queued

        count = recover_interrupted_jobs(session)

        assert count == 1
        session.refresh(job1)
        assert job1.status == JobStatus.queued
        assert job1.worker_id is None

        session.refresh(job2)
        assert job2.status == JobStatus.queued
