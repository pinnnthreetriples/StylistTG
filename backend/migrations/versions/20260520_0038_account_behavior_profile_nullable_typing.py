"""Make typing_speed_baseline_cpm nullable for aggressive mode.

Phase 2 Task 14 bug-fix: aggressive preset should disable typing
simulation (typing_speed_baseline_cpm = NULL).

Revision ID: 20260520_0038
Revises: 20260520_0037
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0038"
down_revision = "20260520_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("account_behavior_profile") as batch_op:
        batch_op.alter_column(
            "typing_speed_baseline_cpm",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE account_behavior_profile "
        "SET typing_speed_baseline_cpm = 120 "
        "WHERE typing_speed_baseline_cpm IS NULL"
    )
    with op.batch_alter_table("account_behavior_profile") as batch_op:
        batch_op.alter_column(
            "typing_speed_baseline_cpm",
            existing_type=sa.Integer(),
            nullable=False,
        )
