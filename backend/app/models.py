from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
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
        UniqueConstraint("external_auth_provider", "external_auth_user_id", name="uq_user_external_auth"),
        Index("ix_user_email", "email"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_auth_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_auth_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owned_workspaces: Mapped[list[Workspace]] = relationship(back_populates="owner")
    memberships: Mapped[list[WorkspaceMember]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspace"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspace_slug"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkspaceStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owner: Mapped[User] = relationship(back_populates="owned_workspaces", foreign_keys=[owner_user_id])
    members: Mapped[list[WorkspaceMember]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_member"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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


class WorkspacePlan(Base):
    __tablename__ = "workspace_plan"

    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    billing_status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    max_accounts: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_jobs_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    max_batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=10240)
    max_team_members: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class UsageCounter(Base):
    __tablename__ = "usage_counter"
    __table_args__ = (
        UniqueConstraint("workspace_id", "period_start", "period_end", "metric", name="uq_usage_counter_period_metric"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
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

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    external_ref: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(64), nullable=False, default="otp")
    account_state: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AccountState.REGISTERED
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
    operation_logs: Mapped[list[AccountOperationLog]] = relationship(
        cascade="all, delete-orphan"
    )
    proxy: Mapped[AccountProxy | None] = relationship(
        cascade="all, delete-orphan", uselist=False
    )
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


class AccountLifecycleEvent(Base):
    __tablename__ = "account_lifecycle_event"
    __table_args__ = (
        Index("ix_account_lifecycle_workspace_created", "workspace_id", "created_at"),
        Index("ix_account_lifecycle_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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

    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), primary_key=True
    )
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
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=True, index=True)
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
    created_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account | None] = relationship(back_populates="telegram_auth_sessions")


class WarmupStrategy(Base):
    __tablename__ = "warmup_strategy"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_warmup_strategy_workspace_name"),
        Index("ix_warmup_strategy_workspace_id", "workspace_id"),
        Index("ix_warmup_strategy_preset", "is_preset"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier_limits_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_channels_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    sessions: Mapped[list[WarmupSession]] = relationship(back_populates="strategy")


class WarmupSession(Base):
    __tablename__ = "warmup_session"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validating', 'scheduled', 'active', 'paused_risk', 'paused_manual', 'completed', 'failed')",
            name="ck_warmup_session_status",
        ),
        CheckConstraint("current_day BETWEEN 0 AND 14", name="ck_warmup_session_current_day"),
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
            postgresql_where=text("status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"),
            sqlite_where=text("status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    strategy_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("warmup_strategy.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    account: Mapped[Account] = relationship(back_populates="warmup_sessions")
    strategy: Mapped[WarmupStrategy] = relationship(back_populates="sessions")
    events: Mapped[list[WarmupEvent]] = relationship(back_populates="session", cascade="all, delete-orphan")
    task_runs: Mapped[list[WarmupTaskRun]] = relationship(back_populates="session", cascade="all, delete-orphan")


class WarmupEvent(Base):
    __tablename__ = "warmup_event"
    __table_args__ = (
        Index("ix_warmup_event_workspace_id", "workspace_id"),
        Index("ix_warmup_event_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("warmup_session.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[WarmupSession] = relationship(back_populates="events")


class WarmupTaskRun(Base):
    __tablename__ = "warmup_task_run"
    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 14", name="ck_warmup_task_run_day"),
        CheckConstraint(
            "status IN ('started', 'completed', 'skipped', 'failed')",
            name="ck_warmup_task_run_status",
        ),
        UniqueConstraint("session_id", "day", "task_type", name="uq_warmup_task_run_session_day_type"),
        Index("ix_warmup_task_run_workspace_id", "workspace_id"),
        Index("ix_warmup_task_run_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("warmup_session.id"), nullable=False)
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


class AccountAuthAttempt(Base):
    __tablename__ = "account_auth_attempt"
    __table_args__ = (
        Index("ix_auth_attempt_account_kind_created", "account_id", "attempt_kind", "created_at"),
        Index("ix_auth_attempt_ref_kind_created", "external_ref", "attempt_kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(128), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="auth_attempts")


class AuthBatch(Base):
    __tablename__ = "auth_batch"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_auth_batch_idempotency_key"),
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
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=AuthBatchItemStatus.QUEUED)
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
        UniqueConstraint("batch_item_id", "attempt_number", "kind", name="uq_auth_attempt_item_number_kind"),
        Index("ix_auth_attempt_batch_item", "batch_item_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_item_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("auth_batch_item.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=AuthAttemptStatus.STARTED)
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
    __table_args__ = (
        Index("ix_idempotency_key_expires", "expires_at"),
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
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
        back_populates="batch", cascade="all, delete-orphan", order_by="AccountImportItem.created_at"
    )


class AccountImportItem(Base):
    __tablename__ = "account_import_item"
    __table_args__ = (
        Index("ix_account_import_item_batch_status", "batch_id", "status"),
        Index("ix_account_import_item_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account_import_batch.id"), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=True)
    source_ref_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    phone_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    batch: Mapped[AccountImportBatch] = relationship(back_populates="items")


class AccountProfileState(Base):
    __tablename__ = "account_profile_state"

    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), primary_key=True
    )
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

    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), primary_key=True
    )
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

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
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

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
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

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
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
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID, index=True
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False, index=True)
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
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tdlib_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tdlib_last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tdlib_last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Job(Base):
    __tablename__ = "job"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
    job_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("job.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("workspace.id"), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDString, ForeignKey("app_user.id"), nullable=True)
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
    storage_migrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
