"""Add neuro commenting foundation."""

from __future__ import annotations

from app.migration_helpers.neuro_commenting_foundation_activity import (
    _create_attempts,
    _create_channel_rules,
    _create_events,
    _create_limits,
    _create_stats,
)
from app.migration_helpers.neuro_commenting_foundation_core import (
    _create_campaign_accounts,
    _create_campaigns,
    _create_generated_comments,
    _create_observed_posts,
    _create_targets,
)
from alembic import op

revision = "20260518_0029"
down_revision = "20260512_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _create_campaigns()
    _create_campaign_accounts()
    _create_targets()
    _create_observed_posts()
    _create_generated_comments()
    _create_attempts()
    _create_events()
    _create_limits()
    _create_stats()
    _create_channel_rules()


def downgrade() -> None:
    op.drop_index(
        "ix_neuro_comment_channel_rule_workspace_ref", table_name="neuro_comment_channel_rules"
    )
    op.drop_table("neuro_comment_channel_rules")
    op.drop_table("neuro_comment_account_stats")
    op.drop_table("neuro_comment_channel_stats")
    op.drop_index("ix_neuro_comment_limit_campaign_scope", table_name="neuro_comment_limits")
    op.drop_table("neuro_comment_limits")
    op.drop_index("ix_neuro_comment_event_campaign_created", table_name="neuro_comment_events")
    op.drop_index("ix_neuro_comment_event_workspace_created", table_name="neuro_comment_events")
    op.drop_table("neuro_comment_events")
    op.drop_index("ix_neuro_comment_attempt_comment", table_name="neuro_comment_attempts")
    op.drop_index("ix_neuro_comment_attempt_campaign_status", table_name="neuro_comment_attempts")
    op.drop_table("neuro_comment_attempts")
    op.drop_index(
        "ix_neuro_comment_generated_approval", table_name="neuro_comment_generated_comments"
    )
    op.drop_index(
        "ix_neuro_comment_generated_campaign_created", table_name="neuro_comment_generated_comments"
    )
    op.drop_table("neuro_comment_generated_comments")
    op.drop_index(
        "ix_neuro_comment_observed_target_seen", table_name="neuro_comment_observed_posts"
    )
    op.drop_index(
        "ix_neuro_comment_observed_campaign_status", table_name="neuro_comment_observed_posts"
    )
    op.drop_table("neuro_comment_observed_posts")
    op.drop_index("ix_neuro_comment_target_channel_id", table_name="neuro_comment_targets")
    op.drop_index("ix_neuro_comment_target_campaign_status", table_name="neuro_comment_targets")
    op.drop_table("neuro_comment_targets")
    op.drop_index(
        "ix_neuro_comment_campaign_account_account", table_name="neuro_comment_campaign_accounts"
    )
    op.drop_index(
        "ix_neuro_comment_campaign_account_campaign", table_name="neuro_comment_campaign_accounts"
    )
    op.drop_table("neuro_comment_campaign_accounts")
    op.drop_index(
        "ix_neuro_comment_campaign_workspace_created", table_name="neuro_comment_campaigns"
    )
    op.drop_index(
        "ix_neuro_comment_campaign_workspace_status", table_name="neuro_comment_campaigns"
    )
    op.drop_table("neuro_comment_campaigns")
