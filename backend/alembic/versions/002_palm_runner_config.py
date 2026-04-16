"""Add palm_runner_config table (ADR-005 runtime config).

Revision ID: 002_palm_runner_config
Revises: 001_baseline
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_palm_runner_config"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "palm_runner_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mode", sa.String, nullable=True),
        sa.Column("remote_url", sa.String, nullable=True),
        sa.Column("remote_token", sa.String, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("updated_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("palm_runner_config")
