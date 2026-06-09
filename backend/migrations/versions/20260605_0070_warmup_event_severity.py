"""Add severity to warmup events.

Revision ID: 20260605_0070
Revises: 20260605_0069
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0070"
down_revision = "20260605_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warmup_event",
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="info",
        ),
    )
    op.create_check_constraint(
        "ck_warmup_event_severity",
        "warmup_event",
        "severity IN ('info', 'success', 'warning', 'error', 'debug')",
    )
    op.create_index(
        "ix_warmup_event_workspace_severity_created",
        "warmup_event",
        ["workspace_id", "severity", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_warmup_event_workspace_severity_created", table_name="warmup_event")
    op.drop_constraint("ck_warmup_event_severity", "warmup_event", type_="check")
    op.drop_column("warmup_event", "severity")
