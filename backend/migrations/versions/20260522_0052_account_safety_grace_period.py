"""Add account safety grace period.

Revision ID: 20260522_0052
Revises: 20260522_0051
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260522_0052"
down_revision = "20260522_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column("safety_grace_period_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_accounts_safety_grace_until",
        "account",
        ["safety_grace_period_until"],
        postgresql_where=sa.text("safety_grace_period_until IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_safety_grace_until", table_name="account")
    op.drop_column("account", "safety_grace_period_until")
