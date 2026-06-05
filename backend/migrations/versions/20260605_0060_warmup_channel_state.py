"""Add warmup channel state table.

Revision ID: 20260605_0060
Revises: 20260604_0059
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260605_0060"
down_revision = "20260604_0059"
branch_labels = None
depends_on = None

uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "warmup_channel_state",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("channel_ref", sa.String(length=255), nullable=False),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_feed_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_story_view_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_react_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_browse_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_stories", sa.Boolean(), nullable=True),
        sa.Column("has_reactions", sa.Boolean(), nullable=True),
        sa.Column(
            "available_reactions_json",
            json_type,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "health_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "fail_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_channel_state_workspace_id"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_warmup_channel_state_account_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_channel_state"),
        sa.UniqueConstraint(
            "workspace_id",
            "account_id",
            "channel_ref",
            name="ix_warmup_channel_state_workspace_account_channel",
        ),
        sa.CheckConstraint(
            "health_score >= 0.0 AND health_score <= 1.0",
            name="ck_warmup_channel_state_health_score",
        ),
        sa.CheckConstraint("success_count >= 0", name="ck_warmup_channel_state_success_count"),
        sa.CheckConstraint("fail_count >= 0", name="ck_warmup_channel_state_fail_count"),
    )
    op.create_index(
        "ix_warmup_channel_state_workspace_id",
        "warmup_channel_state",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_warmup_channel_state_workspace_id", table_name="warmup_channel_state")
    op.drop_table("warmup_channel_state")
