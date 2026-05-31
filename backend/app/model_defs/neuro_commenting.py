from __future__ import annotations

# ruff: noqa: F403,F405

from app.models import *

class NeuroCommentCampaign(Base):
    __tablename__ = "neuro_comment_campaigns"
    __table_args__ = (
        Index("ix_neuro_comment_campaign_workspace_status", "workspace_id", "status"),
        Index("ix_neuro_comment_campaign_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroCampaignStatus.DRAFT
    )
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroCampaignMode.ALL_POSTS
    )
    work_mode: Mapped[str] = mapped_column(String(32), nullable=False, default=NeuroWorkMode.MANUAL)
    approval_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroApprovalMode.MANUAL_REQUIRED
    )
    send_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroSendMode.DRY_RUN
    )
    send_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroSendStrategy.COMMENT
    )
    rotation_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroRotationStrategy.ROUND_ROBIN
    )
    language_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_comments_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_comments_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_comments_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_min_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    delay_max_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    rotate_after_comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_send_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    safety_preset: Mapped[str] = mapped_column(
        String(32), nullable=False, default="balanced", server_default="balanced"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentCampaignAccount(Base):
    __tablename__ = "neuro_comment_campaign_accounts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "account_id", name="uq_neuro_comment_campaign_account"),
        Index("ix_neuro_comment_campaign_account_campaign", "campaign_id"),
        Index("ix_neuro_comment_campaign_account_account", "account_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    rotation_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rotation_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentTarget(Base):
    __tablename__ = "neuro_comment_targets"
    __table_args__ = (
        UniqueConstraint("campaign_id", "channel_ref", name="uq_neuro_comment_target_ref"),
        Index("ix_neuro_comment_target_campaign_status", "campaign_id", "status"),
        Index("ix_neuro_comment_target_channel_id", "channel_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    channel_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discussion_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroTargetStatus.ACTIVE
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="channel")
    activity_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_seen_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_processed_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_commented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    health_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentObservedPost(Base):
    __tablename__ = "neuro_comment_observed_posts"
    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "source_chat_id",
            "source_message_id",
            name="uq_neuro_comment_observed_post_message",
        ),
        Index("ix_neuro_comment_observed_campaign_status", "campaign_id", "status"),
        Index("ix_neuro_comment_observed_target_seen", "target_id", "seen_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_targets.id"), nullable=False
    )
    source_chat_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    discussion_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discussion_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discussion_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    discussion_resolution_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="seen")
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentGeneratedComment(Base):
    __tablename__ = "neuro_comment_generated_comments"
    __table_args__ = (
        Index("ix_neuro_comment_generated_campaign_created", "campaign_id", "created_at"),
        Index("ix_neuro_comment_generated_approval", "approval_status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    target_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_targets.id"), nullable=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    observed_post_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_observed_posts.id"), nullable=True
    )
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    safety_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroSafetyStatus.NEEDS_REVIEW
    )
    safety_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroGeneratedApprovalStatus.PENDING
    )
    approved_by: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentAttempt(Base):
    __tablename__ = "neuro_comment_attempts"
    __table_args__ = (
        UniqueConstraint("generated_comment_id", name="uq_neuro_comment_attempt_generated_comment"),
        Index("ix_neuro_comment_attempt_campaign_status", "campaign_id", "status"),
        Index("ix_neuro_comment_attempt_comment", "generated_comment_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    generated_comment_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_generated_comments.id"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    target_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_targets.id"), nullable=True
    )
    observed_post_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_observed_posts.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroAttemptStatus.CREATED
    )
    send_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NeuroSendStrategy.COMMENT
    )
    telegram_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    flood_wait_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved_limit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    idempotency_key: Mapped[str | None] = mapped_column(UUIDString, nullable=True, unique=True)
    external_message_id_provisional: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentEvent(Base):
    __tablename__ = "neuro_comment_events"
    __table_args__ = (
        Index("ix_neuro_comment_event_workspace_created", "workspace_id", "created_at"),
        Index("ix_neuro_comment_event_campaign_created", "campaign_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    campaign_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    target_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_targets.id"), nullable=True
    )
    observed_post_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_observed_posts.id"), nullable=True
    )
    generated_comment_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_generated_comments.id"), nullable=True
    )
    attempt_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_attempts.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_level: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NeuroCommentLimit(Base):
    __tablename__ = "neuro_comment_limits"
    __table_args__ = (Index("ix_neuro_comment_limit_campaign_scope", "campaign_id", "scope_type"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    limit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    max_value: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentChannelStats(Base):
    __tablename__ = "neuro_comment_channel_stats"
    __table_args__ = (
        UniqueConstraint("campaign_id", "target_id", name="uq_neuro_comment_channel_stats"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_targets.id"), nullable=False
    )
    posts_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentAccountStats(Base):
    __tablename__ = "neuro_comment_account_stats"
    __table_args__ = (
        UniqueConstraint("campaign_id", "account_id", name="uq_neuro_comment_account_stats"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("neuro_comment_campaigns.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    comments_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NeuroCommentChannelRule(Base):
    __tablename__ = "neuro_comment_channel_rules"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "target_ref",
            "rule_type",
            name="uq_neuro_comment_channel_rule_workspace_ref_type",
        ),
        Index("ix_neuro_comment_channel_rule_workspace_ref", "workspace_id", "target_ref"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    target_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
