"""Add cold_soak warmup status.

Revision ID: 20260605_0061
Revises: 20260605_0060
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op


revision = "20260605_0061"
down_revision = "20260605_0060"
branch_labels = None
depends_on = None

OLD_SESSION_STATUSES = (
    "'draft'",
    "'validating'",
    "'scheduled'",
    "'active'",
    "'paused_risk'",
    "'paused_manual'",
    "'completed'",
    "'failed'",
)
NEW_SESSION_STATUSES = OLD_SESSION_STATUSES[:3] + ("'cold_soak'",) + OLD_SESSION_STATUSES[3:]


def upgrade() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.drop_constraint("ck_warmup_session_status", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_session_status",
            f"status IN ({', '.join(NEW_SESSION_STATUSES)})",
        )


def downgrade() -> None:
    op.execute("UPDATE warmup_session SET status = 'scheduled' WHERE status = 'cold_soak'")
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.drop_constraint("ck_warmup_session_status", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_session_status",
            f"status IN ({', '.join(OLD_SESSION_STATUSES)})",
        )
