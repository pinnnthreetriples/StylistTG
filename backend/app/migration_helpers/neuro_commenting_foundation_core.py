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


def _create_campaigns() -> None:
    op.create_table(
        "neuro_comment_campaigns",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="all_posts"),
        sa.Column("work_mode", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column(
            "approval_mode", sa.String(length=32), nullable=False, server_default="manual_required"
        ),
        sa.Column("send_mode", sa.String(length=32), nullable=False, server_default="dry_run"),
        sa.Column("send_strategy", sa.String(length=32), nullable=False, server_default="comment"),
        sa.Column(
            "rotation_strategy", sa.String(length=32), nullable=False, server_default="round_robin"
        ),
        sa.Column("language_mode", sa.String(length=32), nullable=False, server_default="auto"),
        sa.Column("prompt_template", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_comments_total", sa.Integer(), nullable=True),
        sa.Column("max_comments_per_hour", sa.Integer(), nullable=True),
        sa.Column("max_comments_per_day", sa.Integer(), nullable=True),
        sa.Column("delay_min_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("delay_max_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("rotate_after_comments", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_start", sa.String(length=8), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=8), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "auto_send_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("safety_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_neuro_campaign_workspace"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_campaigns"),
    )
    op.create_index(
        "ix_neuro_comment_campaign_workspace_status",
        "neuro_comment_campaigns",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_neuro_comment_campaign_workspace_created",
        "neuro_comment_campaigns",
        ["workspace_id", "created_at"],
    )


def _create_campaign_accounts() -> None:
    op.create_table(
        "neuro_comment_campaign_accounts",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("rotation_weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rotation_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_neuro_campaign_account_account"
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["neuro_comment_campaigns.id"],
            name="fk_neuro_campaign_account_campaign",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_campaign_accounts"),
        sa.UniqueConstraint("campaign_id", "account_id", name="uq_neuro_comment_campaign_account"),
    )
    op.create_index(
        "ix_neuro_comment_campaign_account_campaign",
        "neuro_comment_campaign_accounts",
        ["campaign_id"],
    )
    op.create_index(
        "ix_neuro_comment_campaign_account_account",
        "neuro_comment_campaign_accounts",
        ["account_id"],
    )


def _create_targets() -> None:
    op.create_table(
        "neuro_comment_targets",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("channel_ref", sa.String(length=255), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("discussion_chat_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="channel"),
        sa.Column("activity_level", sa.String(length=32), nullable=True),
        sa.Column("keywords", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("exclude_keywords", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("last_seen_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_processed_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_commented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_score", sa.Float(), nullable=False, server_default="1"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, server_default="0"),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_target_campaign"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_targets"),
        sa.UniqueConstraint("campaign_id", "channel_ref", name="uq_neuro_comment_target_ref"),
    )
    op.create_index(
        "ix_neuro_comment_target_campaign_status",
        "neuro_comment_targets",
        ["campaign_id", "status"],
    )
    op.create_index("ix_neuro_comment_target_channel_id", "neuro_comment_targets", ["channel_id"])


def _create_observed_posts() -> None:
    op.create_table(
        "neuro_comment_observed_posts",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("target_id", uuid_string, nullable=False),
        sa.Column("source_chat_id", sa.String(length=255), nullable=False),
        sa.Column("source_message_id", sa.String(length=255), nullable=False),
        sa.Column("post_text", sa.Text(), nullable=True),
        sa.Column("media_summary", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("matched_mode", sa.String(length=32), nullable=True),
        sa.Column("matched_keywords", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="seen"),
        sa.Column(
            "seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_observed_campaign"
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["neuro_comment_targets.id"], name="fk_neuro_observed_target"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_observed_posts"),
        sa.UniqueConstraint(
            "target_id",
            "source_chat_id",
            "source_message_id",
            name="uq_neuro_comment_observed_post_message",
        ),
    )
    op.create_index(
        "ix_neuro_comment_observed_campaign_status",
        "neuro_comment_observed_posts",
        ["campaign_id", "status"],
    )
    op.create_index(
        "ix_neuro_comment_observed_target_seen",
        "neuro_comment_observed_posts",
        ["target_id", "seen_at"],
    )


def _create_generated_comments() -> None:
    op.create_table(
        "neuro_comment_generated_comments",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("campaign_id", uuid_string, nullable=False),
        sa.Column("target_id", uuid_string, nullable=True),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("observed_post_id", uuid_string, nullable=True),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("edited_text", sa.Text(), nullable=True),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column(
            "safety_status", sa.String(length=32), nullable=False, server_default="needs_review"
        ),
        sa.Column("safety_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "approval_status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column("approved_by", uuid_string, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], name="fk_neuro_generated_account"),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["app_user.id"], name="fk_neuro_generated_approver"
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["neuro_comment_campaigns.id"], name="fk_neuro_generated_campaign"
        ),
        sa.ForeignKeyConstraint(
            ["observed_post_id"],
            ["neuro_comment_observed_posts.id"],
            name="fk_neuro_generated_observed",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["neuro_comment_targets.id"], name="fk_neuro_generated_target"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_neuro_comment_generated_comments"),
    )
    op.create_index(
        "ix_neuro_comment_generated_campaign_created",
        "neuro_comment_generated_comments",
        ["campaign_id", "created_at"],
    )
    op.create_index(
        "ix_neuro_comment_generated_approval",
        "neuro_comment_generated_comments",
        ["approval_status"],
    )
