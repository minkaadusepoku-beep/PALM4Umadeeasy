import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class JobType(str, enum.Enum):
    single = "single"
    comparison = "comparison"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    projects = relationship("Project", back_populates="owner")
    jobs = relationship("Job", back_populates="user")


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

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    job_type = Column(Enum(JobType), nullable=False)
    baseline_scenario_id = Column(Integer, ForeignKey("scenario_records.id"), nullable=False)
    intervention_scenario_id = Column(Integer, ForeignKey("scenario_records.id"), nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.pending, nullable=False)
    output_dir = Column(String, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="jobs")
    project = relationship("Project", back_populates="jobs")
    baseline_scenario = relationship("ScenarioRecord", foreign_keys=[baseline_scenario_id])
    intervention_scenario = relationship("ScenarioRecord", foreign_keys=[intervention_scenario_id])
