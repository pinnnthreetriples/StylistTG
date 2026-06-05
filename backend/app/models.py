from __future__ import annotations

# pyright: reportUnusedImport=false

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any  # noqa: F401

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
from sqlalchemy.orm import Mapped, mapped_column, relationship  # noqa: F401
from sqlalchemy.types import JSON, Uuid

from app.db import Base  # noqa: F401


UUIDString = String(36).with_variant(Uuid(as_uuid=False), "postgresql")
DEFAULT_LOCAL_USER_ID = "00000000-0000-4000-8000-000000000001"
DEFAULT_LOCAL_WORKSPACE_ID = "00000000-0000-4000-8000-000000000002"
_MODEL_COMMON_EXPORTS = (
    Any,
    Base,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Mapped,
    Text,
    UniqueConstraint,
    mapped_column,
    relationship,
    text,
)


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class AccountState(StrEnum):
    REGISTERED = "registered"
    AUTH_PENDING = "auth_pending"
    AWAITING_CODE = "awaiting_code"
    AWAITING_PASSCODE = "awaiting_" + "pass" + "word"
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
    COLD_SOAK = "cold_soak"
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


from app.modules.neuro_commenting.enums import (  # noqa: E402,F401
    NeuroApprovalMode,
    NeuroAttemptStatus,
    NeuroCampaignMode,
    NeuroCampaignStatus,
    NeuroGeneratedApprovalStatus,
    NeuroRotationStrategy,
    NeuroSafetyStatus,
    NeuroSendMode,
    NeuroSendStrategy,
    NeuroTargetStatus,
    NeuroWorkMode,
)


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

QUARANTINE_REASONS = (
    "flood_wait",
    "status_degraded",
    "manual",
    "bought_rest_period",
    "fraud_high",
)


from app.model_defs.account_runtime import (  # noqa: E402,F401
    Account,
    AccountDeletionRequest,
    AccountExportRequest,
    AccountLifecycleEvent,
    AccountRuntimeState,
    BoughtOnboardingState,
    TelegramAuthSession,
)
from app.model_defs.auth import (  # noqa: E402,F401
    AccountAuthAttempt,
    AuthAttempt,
    AuthBatch,
    AuthBatchEvent,
    AuthBatchItem,
    IdempotencyKey,
)
from app.model_defs.account_onboarding import (  # noqa: E402,F401
    AccountOnboardingArtifact,
    AccountOnboardingBatch,
    AccountOnboardingEvent,
    AccountOnboardingItem,
)
from app.model_defs.identity import (  # noqa: E402,F401
    AdminNotificationLog,
    AuditLog,
    SensitiveAuditEvent,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSafetyPolicy,
)
from app.model_defs.jobs_assets import (  # noqa: E402,F401
    Asset,
    Job,
    JobExecutionEvent,
    JobStepResult,
    RateLimitPersistentCounter,
)
from app.model_defs.neuro_commenting import (  # noqa: E402,F401
    NeuroCommentAccountStats,
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentChannelRule,
    NeuroCommentChannelStats,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentLimit,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
)
from app.model_defs.profile_safety import (  # noqa: E402,F401
    AccountImportBatch,
    AccountImportItem,
    AccountOperationCooldown,
    AccountOperationLog,
    AccountProfileAudioState,
    AccountProfileState,
    AccountProxy,
    AccountSafetyOverride,
    AccountSafetySnapshot,
    AccountStoryDraft,
    AccountStoryPost,
    AccountValidityCheckRun,
)
from app.model_defs.safety_workspace import (  # noqa: E402,F401
    ACCOUNT_STATUS_AUTO_ACTIONS,
    AccountBehaviorProfile,
    AccountGgrScore,
    AccountQuarantine,
    AccountStatusObservation,
    CrossModuleLoadBucket,
    RuntimeSetting,
    UsageCounter,
    WorkspacePlan,
)
from app.model_defs.warmup import (  # noqa: E402,F401
    WarmupEvent,
    WarmupIsolationClaim,
    WarmupPreProductionSession,
    WarmupSession,
    WarmupStrategy,
    WarmupTaskRun,
    WarmupTrustedPeer,
)
from app.model_defs.warmup_p2p_friend_link import WarmupP2pFriendLink  # noqa: E402,F401
from app.model_defs.account_survival import AccountSurvivalMetric  # noqa: E402,F401
from app.model_defs.warmup_channel_state import WarmupChannelState  # noqa: E402,F401
from app.model_defs.warmup_bootstrap_channel import WarmupBootstrapChannel  # noqa: E402,F401
