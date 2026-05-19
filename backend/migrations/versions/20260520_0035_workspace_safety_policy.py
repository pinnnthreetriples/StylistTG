"""Create workspace safety policy table.

Revision ID: 20260520_0035
Revises: 20260520_0033
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0035"
down_revision = "20260520_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_safety_policy",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="balanced"),
        sa.Column("delay_multiplier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "typing_chars_per_minute_min",
            sa.Integer(),
            nullable=True,
            server_default="100",
        ),
        sa.Column(
            "typing_chars_per_minute_max",
            sa.Integer(),
            nullable=True,
            server_default="150",
        ),
        sa.Column("profile_view_probability", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("scroll_probability", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("typo_probability", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column(
            "message_deletion_probability",
            sa.Float(),
            nullable=False,
            server_default="0.02",
        ),
        sa.Column("quiet_hours_local_start", sa.Integer(), nullable=True, server_default="120"),
        sa.Column("quiet_hours_local_end", sa.Integer(), nullable=True, server_default="360"),
        sa.Column(
            "require_warmup_before_commenting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("min_warmup_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "require_healthy_proxy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("min_account_age_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column(
            "auto_pause_on_flood_wait_count",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "auto_pause_on_deleted_comments_count",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "quarantine_hours_on_flood_wait",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_safety_policy_workspace"),
        sa.CheckConstraint(
            "mode in ('conservative', 'balanced', 'aggressive')",
            name="ck_workspace_safety_policy_mode",
        ),
    )
    op.create_index(
        "ix_workspace_safety_policy_workspace_id",
        "workspace_safety_policy",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_safety_policy_workspace_id", table_name="workspace_safety_policy")
    op.drop_table("workspace_safety_policy")
