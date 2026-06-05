"""Add account profile uniqueness hashes.

Revision ID: 20260605_0069
Revises: 20260605_0068
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0069"
down_revision = "20260605_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_profile_state",
        sa.Column("bio_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "account_profile_state",
        sa.Column("photo_perceptual_hash", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_account_profile_state_bio_hash",
        "account_profile_state",
        ["bio_hash"],
    )
    op.create_index(
        "ix_account_profile_state_photo_perceptual_hash",
        "account_profile_state",
        ["photo_perceptual_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_profile_state_photo_perceptual_hash",
        table_name="account_profile_state",
    )
    op.drop_index("ix_account_profile_state_bio_hash", table_name="account_profile_state")
    op.drop_column("account_profile_state", "photo_perceptual_hash")
    op.drop_column("account_profile_state", "bio_hash")
