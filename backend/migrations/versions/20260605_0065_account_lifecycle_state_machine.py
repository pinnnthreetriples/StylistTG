"""Add account lifecycle state machine fields.

Revision ID: 20260605_0065
Revises: 20260605_0064
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0065"
down_revision = "20260605_0064"
branch_labels = None
depends_on = None

LIFECYCLE_STATES = (
    "imported",
    "cold_soak",
    "warming",
    "pre_production",
    "active",
    "idle",
    "retired",
    "banned",
    "deleted",
)


def upgrade() -> None:
    states_sql = ",".join(f"'{state}'" for state in LIFECYCLE_STATES)
    with op.batch_alter_table("account") as batch_op:
        batch_op.add_column(
            sa.Column(
                "lifecycle_state",
                sa.String(length=32),
                nullable=False,
                server_default="imported",
            )
        )
        batch_op.add_column(
            sa.Column("lifecycle_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_accounts_lifecycle_state_valid",
            f"lifecycle_state IN ({states_sql})",
        )

    with op.batch_alter_table("account_lifecycle_event") as batch_op:
        batch_op.add_column(sa.Column("from_state", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("to_state", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("account_lifecycle_event") as batch_op:
        batch_op.drop_column("occurred_at")
        batch_op.drop_column("reason")
        batch_op.drop_column("to_state")
        batch_op.drop_column("from_state")

    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_constraint("ck_accounts_lifecycle_state_valid", type_="check")
        batch_op.drop_column("lifecycle_updated_at")
        batch_op.drop_column("lifecycle_state")
