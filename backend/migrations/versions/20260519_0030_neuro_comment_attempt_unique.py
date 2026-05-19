"""Add unique generated-comment attempt constraint.

Revision ID: 20260519_0030
Revises: 20260518_0029
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op


revision = "20260519_0030"
down_revision = "20260518_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_neuro_comment_attempt_generated_comment",
        "neuro_comment_attempts",
        ["generated_comment_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_neuro_comment_attempt_generated_comment",
        "neuro_comment_attempts",
        type_="unique",
    )
