"""Add rate_limit_persistent_counters table for Redis fallback.

Revision ID: 20260521_0050
Revises: 20260520_0049
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260521_0050"
down_revision = "20260520_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_persistent_counters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
            name="uq_rate_limit_persistent_counters_scope_window",
        ),
        sa.Index(
            "ix_rate_limit_persistent_counters_scope",
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
        ),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_persistent_counters")
