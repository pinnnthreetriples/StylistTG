"""Add warmup cyclic session config.

Revision ID: 20260605_0067
Revises: 20260605_0066
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0067"
down_revision = "20260605_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.add_column(sa.Column("cycle_config_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.drop_column("cycle_config_json")
