"""Add warmup bootstrap channels.

Revision ID: 20260605_0068
Revises: 20260605_0067
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0068"
down_revision = "20260605_0067"
branch_labels = None
depends_on = None

uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "warmup_bootstrap_channel",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("channel_ref", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=True),
        sa.Column(
            "verified_safe_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("added_by", uuid_string, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.ForeignKeyConstraint(["added_by"], ["app_user.id"], name="fk_warmup_bootstrap_added_by"),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_bootstrap_channel"),
        sa.UniqueConstraint("channel_ref", name="uq_warmup_bootstrap_channel_ref"),
        sa.CheckConstraint(
            "channel_ref LIKE '@%'",
            name="ck_warmup_bootstrap_channel_ref_public",
        ),
        sa.CheckConstraint(
            "category IN ('news','tech','lifestyle','sports','entertainment','business')",
            name="ck_warmup_bootstrap_channel_category",
        ),
    )
    op.create_index(
        "ix_warmup_bootstrap_channel_category",
        "warmup_bootstrap_channel",
        ["category"],
    )
    op.create_index(
        "ix_warmup_bootstrap_channel_language_country",
        "warmup_bootstrap_channel",
        ["language", "country"],
    )
    op.create_index(
        "ix_warmup_bootstrap_channel_is_active",
        "warmup_bootstrap_channel",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_warmup_bootstrap_channel_is_active", table_name="warmup_bootstrap_channel")
    op.drop_index(
        "ix_warmup_bootstrap_channel_language_country",
        table_name="warmup_bootstrap_channel",
    )
    op.drop_index("ix_warmup_bootstrap_channel_category", table_name="warmup_bootstrap_channel")
    op.drop_table("warmup_bootstrap_channel")
