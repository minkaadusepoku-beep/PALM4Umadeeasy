import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class JobType(str, enum.Enum):
    single = "single"
    comparison = "comparison"


class JobStatus(str, enum.Enum):
    queued = "queued"
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProjectRole(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    projects = relationship("Project", back_populates="owner")
    jobs = relationship("Job", back_populates="user")
    memberships = relationship("ProjectMember", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="projects")
    scenarios = relationship("ScenarioRecord", back_populates="project")
    jobs = relationship("Job", back_populates="project")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(ProjectRole), nullable=False, default=ProjectRole.viewer)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="memberships")


class ScenarioRecord(Base):
    __tablename__ = "scenario_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    scenario_type = Column(String, nullable=False)
    scenario_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="scenarios")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_priority", "status", "priority"),
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_user_id", "user_id"),
        Index("ix_jobs_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    job_type = Column(Enum(JobType), nullable=False)
    baseline_scenario_id = Column(Integer, ForeignKey("scenario_records.id"), nullable=False)
    intervention_scenario_id = Column(Integer, ForeignKey("scenario_records.id"), nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.queued, nullable=False)
    output_dir = Column(String, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Queue fields
    worker_id = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    priority = Column(Integer, default=0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    queued_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="jobs")
    project = relationship("Project", back_populates="jobs")
    baseline_scenario = relationship("ScenarioRecord", foreign_keys=[baseline_scenario_id])
    intervention_scenario = relationship("ScenarioRecord", foreign_keys=[intervention_scenario_id])


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_action", "action"),
        Index("ix_audit_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
