"""Add account safety override audit table.

Revision ID: 20260430_0016
Revises: 20260430_0015
Create Date: 2026-04-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_0016"
down_revision = "20260430_0015"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_safety_override",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_blockers_json", sa.JSON(), nullable=False),
        sa.Column("allowed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_safety_override_account_id", "account_safety_override", ["account_id"])
    op.create_index("ix_account_safety_override_operation", "account_safety_override", ["operation"])


def downgrade() -> None:
    op.drop_index("ix_account_safety_override_operation", table_name="account_safety_override")
    op.drop_index("ix_account_safety_override_account_id", table_name="account_safety_override")
    op.drop_table("account_safety_override")
