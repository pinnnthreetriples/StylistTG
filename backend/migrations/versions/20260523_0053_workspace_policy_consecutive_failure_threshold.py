"""Add workspace policy consecutive failure threshold.

Revision ID: 20260523_0053
Revises: 20260522_0052
Create Date: 2026-05-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260523_0053"
down_revision = "20260522_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_safety_policy",
        sa.Column("consecutive_failure_threshold", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_workspace_safety_policy_consecutive_failure_threshold",
        "workspace_safety_policy",
        "consecutive_failure_threshold IS NULL OR consecutive_failure_threshold BETWEEN 1 AND 20",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_workspace_safety_policy_consecutive_failure_threshold",
        "workspace_safety_policy",
        type_="check",
    )
    op.drop_column("workspace_safety_policy", "consecutive_failure_threshold")
