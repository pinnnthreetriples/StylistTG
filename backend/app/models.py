from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db import Base

UUIDString = String(36).with_variant(Uuid(as_uuid=False), "postgresql")
DEFAULT_LOCAL_USER_ID = "00000000-0000-4000-8000-000000000001"
DEFAULT_LOCAL_WORKSPACE_ID = "00000000-0000-4000-8000-000000000002"


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class AccountState(StrEnum):
    REGISTERED = "registered"
    AUTH_PENDING = "auth_pending"
    AWAITING_CODE = "awaiting_code"
    AWAITING_PASSWORD = "awaiting_password"
    AUTHORIZED_READY = "authorized_ready"
    EXECUTION_USABLE = "execution_usable"
    REAUTH_REQUIRED = "reauth_required"
    RUNTIME_BROKEN = "runtime_broken"
    MANUAL_INTERVENTION_NEEDED = "manual_intervention_needed"
    DISABLED = "disabled"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint(
            "external_auth_provider", "external_auth_user_id", name="uq_user_external_auth"
        ),
        Index("ix_user_email", "email"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_auth_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_auth_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owned_workspaces: Mapped[list[Workspace]] = relationship(back_populates="owner")
    memberships: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspace"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspace_slug"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkspaceStatus.ACTIVE)
    safety_pipeline_v2_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    notification_webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    owner: Mapped[User] = relationship(
        back_populates="owned_workspaces", foreign_keys=[owner_user_id]
    )
    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_member"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SensitiveAuditEvent(Base):
    __tablename__ = "sensitive_audit_event"
    __table_args__ = (
        Index("ix_sensitive_audit_workspace_created", "workspace_id", "created_at"),
        Index("ix_sensitive_audit_account_created", "account_id", "created_at"),
        Index("ix_sensitive_audit_action_created", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    account_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdminNotificationLog(Base):
    __tablename__ = "admin_notification_log"
    __table_args__ = (
        Index(
            "ix_admin_notification_log_ws_trigger_time",
            "workspace_id",
            "trigger_code",
            "triggered_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    trigger_code: Mapped[str] = mapped_column(String(64), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    delivered_channels: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )


class WorkspaceSafetyPolicy(Base):
    __tablename__ = "workspace_safety_policy"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_safety_policy_workspace"),
        CheckConstraint(
            "mode in ('conservative', 'balanced', 'aggressive')",
            name="ck_workspace_safety_policy_mode",
        ),
        CheckConstraint(
            "consecutive_failure_threshold IS NULL OR "
            "consecutive_failure_threshold BETWEEN 1 AND 20",
            name="ck_workspace_safety_policy_consecutive_failure_threshold",
        ),
        Index("ix_workspace_safety_policy_workspace_id", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="balanced")
    delay_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    typing_chars_per_minute_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    typing_chars_per_minute_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_view_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    scroll_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    typo_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    message_deletion_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    quiet_hours_local_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_local_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_warmup_before_commenting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    min_warmup_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    require_healthy_proxy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_account_age_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    auto_pause_on_flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    auto_pause_on_deleted_comments_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5
    )
    quarantine_hours_on_flood_wait: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    consecutive_failure_threshold: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


QUARANTINE_REASONS = (
    "flood_wait",
    "status_degraded",
    "manual",
    "bought_rest_period",
    "fraud_high",
)


class AccountQuarantine(Base):
    __tablename__ = "account_quarantines"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('flood_wait', 'status_degraded', 'manual', 'bought_rest_period', 'fraud_high')",
            name="ck_account_quarantines_reason",
        ),
        Index(
            "ix_account_quarantines_ws_account_until",
            "workspace_id",
            "account_id",
            "until",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


ACCOUNT_STATUS_AUTO_ACTIONS = ("paused", "quarantine", "cooldown", "none")


class AccountStatusObservation(Base):
    __tablename__ = "account_status_observations"
    __table_args__ = (
        CheckConstraint(
            "auto_action_taken IS NULL OR auto_action_taken IN ('paused', 'quarantine', 'cooldown', 'none')",
            name="ck_account_status_observations_auto_action",
        ),
        Index(
            "ix_account_status_observations_account_observed",
            "account_id",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    proxy_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proxy_ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    tdlib_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    device_model_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_action_taken: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CrossModuleLoadBucket(Base):
    __tablename__ = "cross_module_load_buckets"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            "bucket_start",
            name="uq_cross_module_load_buckets_ws_account_bucket",
        ),
        Index("ix_cross_module_load_buckets_bucket_start", "bucket_start"),
        Index(
            "ix_cross_module_load_buckets_account_bucket_start",
            "account_id",
            "bucket_start",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warmup_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commenting_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    editing_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    other_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_actions: Mapped[int] = mapped_column(
        Integer,
        Computed(
            "warmup_actions + commenting_actions + editing_actions + other_actions",
            persisted=True,
        ),
        nullable=False,
    )


class AccountGgrScore(Base):
    __tablename__ = "account_ggr_scores"
    __table_args__ = (
        UniqueConstraint("workspace_id", "account_id", name="uq_account_ggr_scores_ws_account"),
        CheckConstraint("score >= 1.0 AND score <= 10.0", name="ck_account_ggr_scores_range"),
        CheckConstraint(
            "bucket IN ('strong', 'medium', 'weak')",
            name="ck_account_ggr_scores_bucket",
        ),
        Index("ix_account_ggr_scores_workspace_id", "workspace_id"),
        Index("ix_account_ggr_scores_account_id", "account_id"),
        Index("ix_account_ggr_scores_next_calculation", "next_calculation_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    bucket: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_calculation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountBehaviorProfile(Base):
    __tablename__ = "account_behavior_profile"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "account_id", name="uq_account_behavior_profile_ws_account"
        ),
        Index("ix_account_behavior_profile_workspace_id", "workspace_id"),
        Index("ix_account_behavior_profile_account_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    typing_speed_baseline_cpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    typo_rate_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    profile_view_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    scroll_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    message_deletion_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    action_sequence_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    last_randomization_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WorkspacePlan(Base):
    __tablename__ = "workspace_plan"

    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), primary_key=True
    )
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    billing_status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    max_accounts: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_jobs_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    max_batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=10240)
    max_team_members: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RuntimeSetting(Base):
    __tablename__ = "runtime_setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UsageCounter(Base):
    __tablename__ = "usage_counter"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "period_start",
            "period_end",
            "metric",
            name="uq_usage_counter_period_metric",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AuthBatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuthBatchItemStatus(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    WAITING_CODE = "waiting_code"
    WAITING_2FA = "waiting_2fa"
    AUTHORIZED = "authorized"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class AuthAttemptKind(StrEnum):
    START_AUTH = "start_auth"
    SUBMIT_CODE = "submit_code"
    SUBMIT_2FA = "submit_2fa"
    RESEND_CODE = "resend_code"


class AuthAttemptStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class JobState(StrEnum):
    QUEUED = "queued"
    DEDUP_BLOCKED = "dedup_blocked"
    WAITING_LOCK = "waiting_lock"
    RUNNING = "running"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    MANUAL_INTERVENTION_NEEDED = "manual_intervention_needed"
    CANCELED = "canceled"


class StepStatus(StrEnum):
    PLANNED = "planned"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"


class AssetKind(StrEnum):
    PROFILE_PHOTO = "profile_photo"
    PROFILE_AUDIO = "profile_audio"
    STORY_IMAGE = "story_image"
    STORY_VIDEO = "story_video"


class AssetStatus(StrEnum):
    UPLOADED = "uploaded"
    NORMALIZED = "normalized"
    FAILED = "failed"
    ORPHANED = "orphaned"


class WarmupStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED_RISK = "paused_risk"
    PAUSED_MANUAL = "paused_manual"
    COMPLETED = "completed"
    FAILED = "failed"


class WarmupTaskRunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WarmupExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    PASSIVE = "passive"
    NETWORK = "network"
    ADVANCED = "advanced"


class WarmupPresetKind(StrEnum):
    EXPRESS = "express"
    STANDARD = "standard"
    HARDENED = "hardened"
    CUSTOM = "custom"


class NeuroCampaignStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class NeuroCampaignMode(StrEnum):
    ALL_POSTS = "all_posts"
    KEYWORD_MATCH = "keyword_match"
    RANDOM_POSTS = "random_posts"
    SEMANTIC_MATCH = "semantic_match"


class NeuroWorkMode(StrEnum):
    BY_COMMENT_COUNT = "by_comment_count"
    BY_TIME_WINDOW = "by_time_window"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class NeuroApprovalMode(StrEnum):
    MANUAL_REQUIRED = "manual_required"
    TRUSTED_AUTO = "trusted_auto"
    AUTO = "auto"


class NeuroSendMode(StrEnum):
    DRY_RUN = "dry_run"
    MANUAL_APPROVAL = "manual_approval"
    SEMI_AUTO = "semi_auto"
    AUTO = "auto"


class NeuroSendStrategy(StrEnum):
    COMMENT = "comment"
    COMMENT_AS_CHANNEL = "comment_as_channel"
    EMOJI_THEN_EDIT = "emoji_then_edit"


class NeuroRotationStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_USED = "least_used"
    RANDOM = "random"


class NeuroTargetStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    NO_DISCUSSION = "no_discussion"
    BLACKLISTED = "blacklisted"
    FAILED = "failed"
    ARCHIVED = "archived"


class NeuroGeneratedApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPIRED = "expired"


class NeuroAttemptStatus(StrEnum):
    CREATED = "created"
    RESERVED = "reserved"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    FLOOD_WAIT = "flood_wait"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class NeuroSafetyStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


class ProxyCategory(StrEnum):
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    UNKNOWN = "unknown"


ACTIVE_WARMUP_STATUSES = {
    WarmupStatus.VALIDATING,
    WarmupStatus.SCHEDULED,
    WarmupStatus.ACTIVE,
    WarmupStatus.PAUSED_RISK,
    WarmupStatus.PAUSED_MANUAL,
}


TERMINAL_JOB_STATES = {
    JobState.DEDUP_BLOCKED,
    JobState.PARTIALLY_COMPLETED,
    JobState.COMPLETED,
    JobState.FAILED,
    JobState.MANUAL_INTERVENTION_NEEDED,
    JobState.CANCELED,
}

TERMINAL_AUTH_BATCH_STATUSES = {
    AuthBatchStatus.COMPLETED,
    AuthBatchStatus.FAILED,
    AuthBatchStatus.CANCELLED,
}

TERMINAL_AUTH_BATCH_ITEM_STATUSES = {
    AuthBatchItemStatus.AUTHORIZED,
    AuthBatchItemStatus.FAILED,
    AuthBatchItemStatus.CANCELLED,
    AuthBatchItemStatus.TIMED_OUT,
    AuthBatchItemStatus.SKIPPED,
}


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_ref", name="uq_account_workspace_external_ref"),
        CheckConstraint(
            "origin IN ('imported','bought','created')",
            name="ck_accounts_origin_valid",
        ),
        CheckConstraint(
            "terminal_status IN ('none','banned','deleted','suspended')",
            name="ck_accounts_terminal_status_valid",
        ),
        Index("ix_account_workspace_updated", "workspace_id", "updated_at"),
        Index(
            "ix_accounts_safety_grace_until",
            "safety_grace_period_until",
            postgresql_where=text("safety_grace_period_until IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned_channel_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(64), nullable=False, default="otp")
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="imported", server_default="imported"
    )
    account_state: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AccountState.REGISTERED
    )
    terminal_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", server_default="none"
    )
    safety_grace_period_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    runtime_state: Mapped[AccountRuntimeState] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    profile_state: Mapped[AccountProfileState | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    profile_audio_state: Mapped[AccountProfileAudioState | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    story_posts: Mapped[list[AccountStoryPost]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    story_drafts: Mapped[list[AccountStoryDraft]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    safety_snapshot: Mapped[AccountSafetySnapshot | None] = relationship(
        cascade="all, delete-orphan", uselist=False
    )
    validity_check_runs: Mapped[list[AccountValidityCheckRun]] = relationship(
        cascade="all, delete-orphan"
    )
    operation_cooldowns: Mapped[list[AccountOperationCooldown]] = relationship(
        cascade="all, delete-orphan"
    )
    safety_overrides: Mapped[list[AccountSafetyOverride]] = relationship(
        cascade="all, delete-orphan"
    )
    operation_logs: Mapped[list[AccountOperationLog]] = relationship(cascade="all, delete-orphan")
    proxy: Mapped[AccountProxy | None] = relationship(cascade="all, delete-orphan", uselist=False)
    jobs: Mapped[list[Job]] = relationship(back_populates="account")
    auth_attempts: Mapped[list[AccountAuthAttempt]] = relationship(back_populates="account")
    deletion_requests: Mapped[list[AccountDeletionRequest]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    export_requests: Mapped[list[AccountExportRequest]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    telegram_auth_sessions: Mapped[list[TelegramAuthSession]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    warmup_sessions: Mapped[list[WarmupSession]] = relationship(back_populates="account")


class BoughtOnboardingState(Base):
    __tablename__ = "bought_onboarding_state"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_bought_onboarding_state_ws_account",
        ),
        CheckConstraint(
            "current_step IN ('enable_2fa','terminate_other_sessions','rest_period','ggr_precheck','completed')",
            name="ck_bought_onboarding_state_current_step",
        ),
        Index("ix_bought_onboarding_state_workspace_account", "workspace_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_step: Mapped[str] = mapped_column(String(64), nullable=False, default="enable_2fa")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AccountLifecycleEvent(Base):
    __tablename__ = "account_lifecycle_event"
    __table_args__ = (
        Index("ix_account_lifecycle_workspace_created", "workspace_id", "created_at"),
        Index("ix_account_lifecycle_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    request_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_request"
    __table_args__ = (
        Index("ix_account_deletion_workspace_status", "workspace_id", "status"),
        Index("ix_account_deletion_account_status", "account_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account] = relationship(back_populates="deletion_requests")


class AccountExportRequest(Base):
    __tablename__ = "account_export_request"
    __table_args__ = (
        Index("ix_account_export_workspace_status", "workspace_id", "status"),
        Index("ix_account_export_account_created", "account_id", "requested_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    export_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    export_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account] = relationship(back_populates="export_requests")


class AccountRuntimeState(Base):
    __tablename__ = "account_runtime_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    session_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authorized_last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime_health: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    reauth_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lock_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovery_marker: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="runtime_state")


class TelegramAuthSession(Base):
    __tablename__ = "telegram_auth_session"
    __table_args__ = (
        Index("ix_telegram_auth_session_workspace_status", "workspace_id", "status"),
        Index("ix_telegram_auth_session_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=True, index=True
    )
    phone_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="new_auth")
    tdlib_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account | None] = relationship(back_populates="telegram_auth_sessions")


class WarmupStrategy(Base):
    __tablename__ = "warmup_strategy"
    __table_args__ = (
        CheckConstraint(
            "execution_mode IN ('dry_run', 'shadow', 'passive', 'network', 'advanced')",
            name="ck_warmup_strategy_execution_mode",
        ),
        CheckConstraint(
            "preset_kind IN ('express', 'standard', 'hardened', 'custom')",
            name="ck_warmup_strategy_preset_kind",
        ),
        CheckConstraint("duration_days BETWEEN 3 AND 30", name="ck_warmup_strategy_duration_days"),
        UniqueConstraint("workspace_id", "name", name="uq_warmup_strategy_workspace_name"),
        Index("ix_warmup_strategy_workspace_id", "workspace_id"),
        Index("ix_warmup_strategy_preset", "is_preset"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier_limits_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_channels_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupExecutionMode.DRY_RUN
    )
    preset_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupPresetKind.CUSTOM
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    daily_action_limits_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    session_window_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    ui_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list[WarmupSession]] = relationship(back_populates="strategy")


class WarmupSession(Base):
    __tablename__ = "warmup_session"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validating', 'scheduled', 'active', 'paused_risk', 'paused_manual', 'completed', 'failed')",
            name="ck_warmup_session_status",
        ),
        CheckConstraint("current_day BETWEEN 0 AND 30", name="ck_warmup_session_current_day"),
        CheckConstraint("duration_days BETWEEN 3 AND 30", name="ck_warmup_session_duration_days"),
        CheckConstraint("cadence_hours >= 1", name="ck_warmup_session_cadence_hours"),
        CheckConstraint("flood_wait_count >= 0", name="ck_warmup_session_flood_wait_count"),
        CheckConstraint("consecutive_failures >= 0", name="ck_warmup_session_consecutive_failures"),
        Index("ix_warmup_session_workspace_id", "workspace_id"),
        Index("ix_warmup_session_account_id", "account_id"),
        Index("ix_warmup_session_status", "status"),
        Index(
            "ix_warmup_session_due",
            "next_step_at",
            postgresql_where=text("status IN ('scheduled', 'active')"),
            sqlite_where=text("status IN ('scheduled', 'active')"),
        ),
        Index(
            "ux_warmup_session_active_account",
            "workspace_id",
            "account_id",
            unique=True,
            postgresql_where=text(
                "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
            ),
            sqlite_where=text(
                "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_strategy.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WarmupStatus.DRAFT)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cadence_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupExecutionMode.DRY_RUN
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_micro_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_micro_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    daily_counters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trusted_peer_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    proxy_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="warmup_sessions")
    strategy: Mapped[WarmupStrategy] = relationship(back_populates="sessions")
    events: Mapped[list[WarmupEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    task_runs: Mapped[list[WarmupTaskRun]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WarmupEvent(Base):
    __tablename__ = "warmup_event"
    __table_args__ = (
        Index("ix_warmup_event_workspace_id", "workspace_id"),
        Index("ix_warmup_event_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_session.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[WarmupSession] = relationship(back_populates="events")


class WarmupTaskRun(Base):
    __tablename__ = "warmup_task_run"
    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 30", name="ck_warmup_task_run_day"),
        CheckConstraint(
            "status IN ('started', 'completed', 'skipped', 'failed')",
            name="ck_warmup_task_run_status",
        ),
        UniqueConstraint(
            "session_id", "day", "task_type", name="uq_warmup_task_run_session_day_type"
        ),
        Index("ix_warmup_task_run_workspace_id", "workspace_id"),
        Index("ix_warmup_task_run_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_session.id"), nullable=False
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[WarmupSession] = relationship(back_populates="task_runs")


class WarmupTrustedPeer(Base):
    __tablename__ = "warmup_trusted_peer"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "account_id", name="uq_warmup_trusted_peer_workspace_account"
        ),
        Index("ix_warmup_trusted_peer_workspace_eligible", "workspace_id", "eligible_from"),
        CheckConstraint(
            "max_active_contacts >= 0", name="ck_warmup_trusted_peer_max_active_contacts"
        ),
        CheckConstraint("current_contacts >= 0", name="ck_warmup_trusted_peer_current_contacts"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    eligible_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_active_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    current_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WarmupIsolationClaim(Base):
    __tablename__ = "warmup_isolation_claim"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    held_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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


class AccountAuthAttempt(Base):
    __tablename__ = "account_auth_attempt"
    __table_args__ = (
        Index("ix_auth_attempt_account_kind_created", "account_id", "attempt_kind", "created_at"),
        Index("ix_auth_attempt_ref_kind_created", "external_ref", "attempt_kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(128), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="auth_attempts")


class AuthBatch(Base):
    __tablename__ = "auth_batch"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_auth_batch_workspace_idempotency_key"
        ),
        Index("ix_auth_batch_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=AuthBatchStatus.PENDING)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_running_commands: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_waiting_input: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_total_active: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[AuthBatchItem]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="AuthBatchItem.position"
    )
    events: Mapped[list[AuthBatchEvent]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class AuthBatchItem(Base):
    __tablename__ = "auth_batch_item"
    __table_args__ = (
        UniqueConstraint("batch_id", "position", name="uq_auth_batch_item_batch_position"),
        Index("ix_auth_batch_item_batch_status", "batch_id", "status"),
        Index("ix_auth_batch_item_lock_expires", "lock_expires_at"),
        Index("ix_auth_batch_item_phone_status", "phone_number", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("auth_batch.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AuthBatchItemStatus.QUEUED
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    password_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[AuthBatch] = relationship(back_populates="items")
    account: Mapped[Account] = relationship()
    attempts: Mapped[list[AuthAttempt]] = relationship(
        back_populates="batch_item", cascade="all, delete-orphan"
    )
    events: Mapped[list[AuthBatchEvent]] = relationship(back_populates="batch_item")


class AuthAttempt(Base):
    __tablename__ = "auth_attempt"
    __table_args__ = (
        UniqueConstraint(
            "batch_item_id", "attempt_number", "kind", name="uq_auth_attempt_item_number_kind"
        ),
        Index("ix_auth_attempt_batch_item", "batch_item_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_item_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("auth_batch_item.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AuthAttemptStatus.STARTED
    )
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch_item: Mapped[AuthBatchItem] = relationship(back_populates="attempts")


class AuthBatchEvent(Base):
    __tablename__ = "auth_batch_event"
    __table_args__ = (
        Index("ix_auth_batch_event_batch_created", "batch_id", "created_at"),
        Index("ix_auth_batch_event_item_created", "batch_item_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("auth_batch.id"), nullable=False)
    batch_item_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("auth_batch_item.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    batch: Mapped[AuthBatch] = relationship(back_populates="events")
    batch_item: Mapped[AuthBatchItem | None] = relationship(back_populates="events")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"
    __table_args__ = (Index("ix_idempotency_key_expires", "expires_at"),)

    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), primary_key=True, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountImportBatch(Base):
    __tablename__ = "account_import_batch"
    __table_args__ = (
        Index("ix_account_import_batch_workspace_status", "workspace_id", "status"),
        Index("ix_account_import_batch_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="uploaded")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[AccountImportItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AccountImportItem.created_at",
    )


class AccountImportItem(Base):
    __tablename__ = "account_import_item"
    __table_args__ = (
        Index("ix_account_import_item_batch_status", "batch_id", "status"),
        Index("ix_account_import_item_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account_import_batch.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=True
    )
    source_ref_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    phone_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    batch: Mapped[AccountImportBatch] = relationship(back_populates="items")


class AccountProfileState(Base):
    __tablename__ = "account_profile_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_photo_asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="profile_state")


class AccountProfileAudioState(Base):
    __tablename__ = "account_profile_audio_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    telegram_audio_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    performer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    raw_tdlib_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="profile_audio_state")


class AccountStoryPost(Base):
    __tablename__ = "account_story_post"
    __table_args__ = (
        UniqueConstraint("job_id", "step_key", name="uq_account_story_post_job_step"),
        Index("ix_story_post_account_status_created", "account_id", "status", "created_at"),
        Index("ix_story_post_account_asset", "account_id", "asset_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    step_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    story_poster_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_story_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temporary_story_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="contacts")
    active_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    protect_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_be_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="posted")
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_tdlib_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="story_posts")


class AccountStoryDraft(Base):
    __tablename__ = "account_story_draft"
    __table_args__ = (
        Index("ix_story_draft_account_updated", "account_id", "updated_at"),
        Index("ix_story_draft_account_asset", "account_id", "asset_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    media_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="contacts")
    active_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    protect_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="story_drafts")


class AccountSafetySnapshot(Base):
    __tablename__ = "account_safety_snapshot"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    health_status: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_risk_level: Mapped[str] = mapped_column(String(64), nullable=False)
    validity_status: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_by_operation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reasons_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    signals_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="db_snapshot")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountValidityCheckRun(Base):
    __tablename__ = "account_validity_check_run"
    __table_args__ = (Index("ix_validity_check_account_started", "account_id", "started_at"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountOperationCooldown(Base):
    __tablename__ = "account_operation_cooldown"
    __table_args__ = (
        Index("ix_cooldown_account_op_retry", "account_id", "operation", "retry_after_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retry_after_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    source_step_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountSafetyOverride(Base):
    __tablename__ = "account_safety_override"
    __table_args__ = (
        Index("ix_override_account_op_until", "account_id", "operation", "allowed_until"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_blockers_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountOperationLog(Base):
    __tablename__ = "account_operation_log"
    __table_args__ = (
        Index("ix_operation_log_account_created", "account_id", "created_at"),
        Index("ix_operation_log_type_status_created", "operation_type", "status", "created_at"),
        Index("ix_operation_log_workspace_created", "workspace_id", "created_at"),
        Index(
            "ix_operation_log_ws_type_status_created",
            "workspace_id",
            "operation_type",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("workspace.id"),
        nullable=False,
        default=DEFAULT_LOCAL_WORKSPACE_ID,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    step_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountProxy(Base):
    __tablename__ = "account_proxy"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    proxy_type: Mapped[str] = mapped_column(String(16), nullable=False)
    proxy_category: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ProxyCategory.UNKNOWN
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tdlib_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tdlib_last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tdlib_last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        Index("ix_job_account_queued", "account_id", "queued_at"),
        Index("ix_job_workspace_account_queued", "workspace_id", "account_id", "queued_at"),
        Index("ix_job_account_intent_state", "account_id", "execution_intent_hash", "job_state"),
        Index("ix_job_account_finished", "account_id", "finished_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_from: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_state: Mapped[str] = mapped_column(String(64), nullable=False, default=JobState.QUEUED)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, default="profile_update")
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_intent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    job_payload_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    desired_state_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    capability_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    plan_json_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    compensation_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedup_blocked_by_job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account] = relationship(back_populates="jobs")
    step_results: Mapped[list[JobStepResult]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStepResult.started_at"
    )
    execution_events: Mapped[list[JobExecutionEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobExecutionEvent.created_at"
    )


class JobExecutionEvent(Base):
    __tablename__ = "job_execution_event"
    __table_args__ = (
        Index("ix_job_execution_workspace_created", "workspace_id", "created_at"),
        Index("ix_job_execution_account_created", "account_id", "created_at"),
        Index("ix_job_execution_job_created", "job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("job.id"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    queue_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[Job | None] = relationship(back_populates="execution_events")


class JobStepResult(Base):
    __tablename__ = "job_step_result"
    __table_args__ = (
        Index("ix_job_step_result_job_started", "job_id", "started_at"),
        Index("ix_job_step_result_job_status_finished", "job_id", "status", "finished_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("job.id"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=StepStatus.PLANNED)
    step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capability_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compensation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uncertain_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    job: Mapped[Job] = relationship(back_populates="step_results")


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (Index("ix_asset_workspace_storage", "workspace_id", "storage_backend"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_migrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RateLimitPersistentCounter(Base):
    __tablename__ = "rate_limit_persistent_counters"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
            name="uq_rate_limit_persistent_counters_scope_window",
        ),
        Index(
            "ix_rate_limit_persistent_counters_scope",
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
