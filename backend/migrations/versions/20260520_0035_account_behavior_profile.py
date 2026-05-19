"""Create account_behavior_profile table.

Phase 2 Task 14: per-account stable behavior profile for the
HumanBehaviorEmulator layer. Stores randomized-on-first-use
baseline values so each account looks consistently unique.

Revision ID: 20260520_0035
Revises: 20260520_0034
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0035"
down_revision = "20260520_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_behavior_profile",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspace.id"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("account.id"),
            nullable=False,
        ),
        sa.Column("typing_speed_baseline_cpm", sa.Integer(), nullable=False),
        sa.Column("typo_rate_baseline", sa.Float(), nullable=False),
        sa.Column("profile_view_probability_baseline", sa.Float(), nullable=False),
        sa.Column("scroll_probability_baseline", sa.Float(), nullable=False),
        sa.Column("message_deletion_probability_baseline", sa.Float(), nullable=False),
        sa.Column("action_sequence_seed", sa.Integer(), nullable=False),
        sa.Column(
            "last_randomization_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "workspace_id", "account_id", name="uq_account_behavior_profile_ws_account"
        ),
    )
    op.create_index(
        "ix_account_behavior_profile_workspace_id",
        "account_behavior_profile",
        ["workspace_id"],
    )
    op.create_index(
        "ix_account_behavior_profile_account_id",
        "account_behavior_profile",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_behavior_profile_account_id",
        table_name="account_behavior_profile",
    )
    op.drop_index(
        "ix_account_behavior_profile_workspace_id",
        table_name="account_behavior_profile",
    )
    op.drop_table("account_behavior_profile")
