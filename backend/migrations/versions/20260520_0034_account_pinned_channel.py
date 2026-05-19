"""Add pinned_channel_ref column to accounts.

Phase 1 Task 6: pinned channel operation (TDLib setPersonalChat).
Stores the channel username or numeric ID that should be pinned
to the account profile.

Revision ID: 20260520_0034
Revises: 20260520_0033
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0034"
down_revision = "20260520_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column("pinned_channel_ref", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("account", "pinned_channel_ref")
