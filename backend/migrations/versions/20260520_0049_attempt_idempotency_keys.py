"""Add attempt idempotency keys and event outbox is_published.

Revision ID: 20260520_0049
Revises: 20260520_0048
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0049"
down_revision = "20260520_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "neuro_comment_attempts",
        sa.Column("idempotency_key", sa.String(36), nullable=True),
    )
    op.add_column(
        "neuro_comment_attempts",
        sa.Column("external_message_id_provisional", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_attempts_idempotency_key",
        "neuro_comment_attempts",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_attempts_external_message_id_provisional",
        "neuro_comment_attempts",
        ["external_message_id_provisional"],
    )
    op.add_column(
        "neuro_comment_events",
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_neuro_comment_events_unpublished",
        "neuro_comment_events",
        ["is_published", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_neuro_comment_events_unpublished", table_name="neuro_comment_events")
    op.drop_column("neuro_comment_events", "is_published")
    op.drop_index(
        "ix_attempts_external_message_id_provisional",
        table_name="neuro_comment_attempts",
    )
    op.drop_constraint("uq_attempts_idempotency_key", "neuro_comment_attempts", type_="unique")
    op.drop_column("neuro_comment_attempts", "external_message_id_provisional")
    op.drop_column("neuro_comment_attempts", "idempotency_key")
