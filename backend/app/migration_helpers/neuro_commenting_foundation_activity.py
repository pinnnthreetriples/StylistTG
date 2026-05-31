"""Table builders for 20260518_0029 neuro commenting foundation."""

from __future__ import annotations

# pyright: reportReturnType=false, reportUnusedFunction=false

from alembic import op
import sqlalchemy as sa

from app.migration_helpers.neuro_commenting_foundation_common import (
    json_type,
    timestamp_columns,
    uuid_string,
)


def _create_attempts() -> None:
    op.create_table(
        "neuro_comment_attempts",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("generated_comment_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("target_id", uuid_string, nullable=True),
        sa.Column("observed_post_id", uuid_string, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("send_strategy", sa.String(length=32), nullable=False, server_default="comment"),
        sa.Column("telegram_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("flood_wait_seconds", sa.Integer(), nullable=True),
        sa.Column("reserved_limit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], name="fk_neuro_attempt_account"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_attempt_campaign"
        ),
        sa.ForeignKeyConstraint(
            ["generated_comment_id"],
            ["neuro_comment_generated_comments.id"],
            name="fk_neuro_attempt_comment",
        ),
        sa.ForeignKeyConstraint(
            ["observed_post_id"],
            ["neuro_comment_observed_posts.id"],
            name="fk_neuro_attempt_observed",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["neuro_comment_targets.id"], name="fk_neuro_attempt_target"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_attempts"),
    )
    op.create_index(
        "ix_neuro_comment_attempt_campaign_status",
        "neuro_comment_attempts",
        ["campaign_id", "status"],
    )
    op.create_index(
        "ix_neuro_comment_attempt_comment", "neuro_comment_attempts", ["generated_comment_id"]
    )


def _create_events() -> None:
    op.create_table(
        "neuro_comment_events",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=True),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("target_id", uuid_string, nullable=True),
        sa.Column("observed_post_id", uuid_string, nullable=True),
        sa.Column("generated_comment_id", uuid_string, nullable=True),
        sa.Column("attempt_id", uuid_string, nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_level", sa.String(length=32), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], name="fk_neuro_event_account"),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["neuro_comment_attempts.id"], name="fk_neuro_event_attempt"
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_event_campaign"
        ),
        sa.ForeignKeyConstraint(
            ["generated_comment_id"],
            ["neuro_comment_generated_comments.id"],
            name="fk_neuro_event_comment",
        ),
        sa.ForeignKeyConstraint(
            ["observed_post_id"],
            ["neuro_comment_observed_posts.id"],
            name="fk_neuro_event_observed",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["neuro_comment_targets.id"], name="fk_neuro_event_target"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_neuro_event_workspace"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_events"),
    )
    op.create_index(
        "ix_neuro_comment_event_workspace_created",
        "neuro_comment_events",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_neuro_comment_event_campaign_created",
        "neuro_comment_events",
        ["campaign_id", "created_at"],
    )


def _create_limits() -> None:
    op.create_table(
        "neuro_comment_limits",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("scope_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=True),
        sa.Column("limit_type", sa.String(length=64), nullable=False),
        sa.Column("max_value", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_limit_campaign"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_limits"),
    )
    op.create_index(
        "ix_neuro_comment_limit_campaign_scope",
        "neuro_comment_limits",
        ["campaign_id", "scope_type"],
    )


def _create_stats() -> None:
    op.create_table(
        "neuro_comment_channel_stats",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("target_id", uuid_string, nullable=False),
        sa.Column("posts_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_channel_stats_campaign"
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["neuro_comment_targets.id"], name="fk_neuro_channel_stats_target"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_channel_stats"),
        sa.UniqueConstraint("campaign_id", "target_id", name="uq_neuro_comment_channel_stats"),
    )

    op.create_table(
        "neuro_comment_account_stats",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("comments_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_neuro_account_stats_account"
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_account_stats_campaign"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_account_stats"),
        sa.UniqueConstraint("campaign_id", "account_id", name="uq_neuro_comment_account_stats"),
    )


def _create_channel_rules() -> None:
    op.create_table(
        "neuro_comment_channel_rules",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", uuid_string, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_neuro_rule_creator"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], name="fk_neuro_rule_workspace"),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_channel_rules"),
    )
    op.create_index(
        "ix_neuro_comment_channel_rule_workspace_ref",
        "neuro_comment_channel_rules",
        ["workspace_id", "target_ref"],
    )
