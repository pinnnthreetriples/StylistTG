"""Add discussion message mapping to observed posts.

Revision ID: 20260519_0032
Revises: 20260519_0031
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260519_0032"
down_revision = "20260519_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "neuro_comment_observed_posts",
        sa.Column("discussion_chat_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "neuro_comment_observed_posts",
        sa.Column("discussion_message_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "neuro_comment_observed_posts",
        sa.Column("discussion_resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "neuro_comment_observed_posts",
        sa.Column("discussion_resolution_error_code", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("neuro_comment_observed_posts", "discussion_resolution_error_code")
    op.drop_column("neuro_comment_observed_posts", "discussion_resolved_at")
    op.drop_column("neuro_comment_observed_posts", "discussion_message_id")
    op.drop_column("neuro_comment_observed_posts", "discussion_chat_id")
