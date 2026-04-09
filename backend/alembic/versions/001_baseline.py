"""Baseline: all tables as of Phase 3 completion.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("is_admin", sa.Boolean, default=False, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # --- project_members ---
    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Enum("owner", "editor", "viewer", name="projectrole"), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    # --- scenario_records ---
    op.create_table(
        "scenario_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("scenario_type", sa.String, nullable=False),
        sa.Column("scenario_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # --- jobs ---
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_type", sa.Enum("single", "comparison", name="jobtype"), nullable=False),
        sa.Column("baseline_scenario_id", sa.Integer, sa.ForeignKey("scenario_records.id"), nullable=False),
        sa.Column("intervention_scenario_id", sa.Integer, sa.ForeignKey("scenario_records.id"), nullable=True),
        sa.Column("status", sa.Enum("queued", "pending", "running", "completed", "failed", "cancelled", name="jobstatus"), nullable=False),
        sa.Column("output_dir", sa.String, nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("worker_id", sa.String, nullable=True),
        sa.Column("last_heartbeat", sa.DateTime, nullable=True),
        sa.Column("priority", sa.Integer, default=0, nullable=False),
        sa.Column("retry_count", sa.Integer, default=0, nullable=False),
        sa.Column("max_retries", sa.Integer, default=3, nullable=False),
        sa.Column("queued_at", sa.DateTime),
    )
    op.create_index("ix_jobs_status_priority", "jobs", ["status", "priority"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("resource_type", sa.String, nullable=False),
        sa.Column("resource_id", sa.Integer, nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("request_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_audit_action", "audit_log", ["action"])
    op.create_index("ix_audit_created_at", "audit_log", ["created_at"])

    # --- forcing_files ---
    op.create_table(
        "forcing_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("original_name", sa.String, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("validated", sa.Boolean, default=False, nullable=False),
        sa.Column("validation_errors", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("forcing_files")
    op.drop_table("audit_log")
    op.drop_table("jobs")
    op.drop_table("scenario_records")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
