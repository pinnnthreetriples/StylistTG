"""Add safety_preset column to neuro_comment_campaigns.

Phase 1 Task 9 introduces a per-campaign safety preset
(conservative / balanced / aggressive). The default value backfills
existing rows so the column can be made NOT NULL safely.

Revision ID: 20260520_0033
Revises: 20260519_0032
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0033"
down_revision = "20260519_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "neuro_comment_campaigns",
        sa.Column(
            "safety_preset",
            sa.String(length=32),
            nullable=False,
            server_default="balanced",
        ),
    )


def downgrade() -> None:
    op.drop_column("neuro_comment_campaigns", "safety_preset")
