"""Add warmup pre-production session table.

Revision ID: 20260605_0066
Revises: 20260605_0065
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0066"
down_revision = "20260605_0065"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "warmup_pre_production_session",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column(
            "account_id",
            UUID_STRING,
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_warmup_session_id",
            UUID_STRING,
            sa.ForeignKey("warmup_session.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("duration_hours", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("task_plan_json", sa.JSON(), nullable=False),
        sa.Column("task_result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_warmup_pre_production_status",
        ),
        sa.CheckConstraint(
            "duration_hours BETWEEN 1 AND 2",
            name="ck_warmup_pre_production_duration_hours",
        ),
    )
    op.create_index(
        "ix_warmup_pre_production_account_status",
        "warmup_pre_production_session",
        ["workspace_id", "account_id", "status"],
    )
    op.create_index(
        "ix_warmup_pre_production_ends",
        "warmup_pre_production_session",
        ["ends_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_warmup_pre_production_ends", table_name="warmup_pre_production_session")
    op.drop_index(
        "ix_warmup_pre_production_account_status",
        table_name="warmup_pre_production_session",
    )
    op.drop_table("warmup_pre_production_session")
