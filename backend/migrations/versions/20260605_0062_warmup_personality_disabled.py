"""Add warmup session advanced configuration fields.

Revision ID: 20260605_0062
Revises: 20260605_0061
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260605_0062"
down_revision = "20260605_0061"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.add_column(sa.Column("cold_soak_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "personality_seed_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "disabled_actions_json",
                json_type,
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "lifecycle_state",
                sa.String(length=32),
                nullable=False,
                server_default="warming",
            )
        )
        batch_op.add_column(sa.Column("strategy_snapshot_json", json_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.drop_column("strategy_snapshot_json")
        batch_op.drop_column("lifecycle_state")
        batch_op.drop_column("disabled_actions_json")
        batch_op.drop_column("personality_seed_json")
        batch_op.drop_column("cold_soak_until")
