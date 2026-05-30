from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator

from app.contracts import accounts as _account_contracts
from app.contracts import jobs as _job_contracts
from app.contracts import neuro_commenting as _neuro_commenting_contracts
from app.modules.account_ggr import contracts as _ggr_contracts
from app.modules.account_lifecycle import contracts as _account_lifecycle_contracts
from app.modules.account_safety import gate_contracts as _safety_gate_contracts
from app.modules.account_safety import read_contracts as _safety_contracts
from app.modules.bought_onboarding import contracts as _bought_onboarding_contracts
from app.modules.human_behavior import contracts as _human_behavior_contracts
from app.modules.warmup import contracts as _warmup_contracts

TerminalStatus = Literal["none", "banned", "deleted", "suspended"]

ProfileAudioAction = _account_contracts.ProfileAudioAction
ProfilePreviewRead = _account_contracts.ProfilePreviewRead
ProfilePreviewStepRead = _account_contracts.ProfilePreviewStepRead
JobSummaryRead = _job_contracts.JobSummaryRead
AccountCapabilityRead = _safety_contracts.AccountCapabilityRead
AccountOperationCooldownRead = _safety_contracts.AccountOperationCooldownRead
AccountOperationSafetyRead = _safety_contracts.AccountOperationSafetyRead
AccountRiskRead = _safety_contracts.AccountRiskRead
AccountSafetyRead = _safety_contracts.AccountSafetyRead
AccountSafetyReasonRead = _safety_contracts.AccountSafetyReasonRead
AccountSafetySummaryRead = _safety_contracts.AccountSafetySummaryRead
AccountValidityCheckRead = _safety_contracts.AccountValidityCheckRead
WorkspaceSafetyPolicyRead = _safety_gate_contracts.WorkspaceSafetyPolicyRead
WorkspaceSafetyPolicyUpdate = _safety_gate_contracts.WorkspaceSafetyPolicyUpdate
AccountDeletionPlannedActionRead = _account_lifecycle_contracts.AccountDeletionPlannedActionRead
AccountDeletionPreviewRead = _account_lifecycle_contracts.AccountDeletionPreviewRead
AccountDeletionRequestCreate = _account_lifecycle_contracts.AccountDeletionRequestCreate
AccountDeletionRequestRead = _account_lifecycle_contracts.AccountDeletionRequestRead
AccountExportRequestRead = _account_lifecycle_contracts.AccountExportRequestRead
GgrBreakdownRead = _ggr_contracts.GgrBreakdownRead
GgrScoreRead = _ggr_contracts.GgrScoreRead
BehaviorProfileRead = _human_behavior_contracts.BehaviorProfileRead
BoughtOnboardingStatusRead = _bought_onboarding_contracts.BoughtOnboardingStatusRead
NeuroAccountStatsPageRead = _neuro_commenting_contracts.NeuroAccountStatsPageRead
NeuroAccountStatsRead = _neuro_commenting_contracts.NeuroAccountStatsRead
NeuroAttemptPageRead = _neuro_commenting_contracts.NeuroAttemptPageRead
NeuroAttemptRead = _neuro_commenting_contracts.NeuroAttemptRead
NeuroCampaignStatsRead = _neuro_commenting_contracts.NeuroCampaignStatsRead
NeuroChannelStatsPageRead = _neuro_commenting_contracts.NeuroChannelStatsPageRead
NeuroChannelStatsRead = _neuro_commenting_contracts.NeuroChannelStatsRead
NeuroChannelRuleCreate = _neuro_commenting_contracts.NeuroChannelRuleCreate
NeuroChannelRulePageRead = _neuro_commenting_contracts.NeuroChannelRulePageRead
NeuroChannelRuleRead = _neuro_commenting_contracts.NeuroChannelRuleRead
NeuroFailureReasonPageRead = _neuro_commenting_contracts.NeuroFailureReasonPageRead
NeuroFailureReasonRead = _neuro_commenting_contracts.NeuroFailureReasonRead
NeuroCampaignAccountCreate = _neuro_commenting_contracts.NeuroCampaignAccountCreate
NeuroCampaignAccountPageRead = _neuro_commenting_contracts.NeuroCampaignAccountPageRead
NeuroCampaignAccountRead = _neuro_commenting_contracts.NeuroCampaignAccountRead
NeuroCampaignCreate = _neuro_commenting_contracts.NeuroCampaignCreate
NeuroCampaignPageRead = _neuro_commenting_contracts.NeuroCampaignPageRead
NeuroCampaignRead = _neuro_commenting_contracts.NeuroCampaignRead
NeuroCampaignUpdate = _neuro_commenting_contracts.NeuroCampaignUpdate
NeuroEventPageRead = _neuro_commenting_contracts.NeuroEventPageRead
NeuroEventRead = _neuro_commenting_contracts.NeuroEventRead
NeuroGeneratedCommentPageRead = _neuro_commenting_contracts.NeuroGeneratedCommentPageRead
NeuroGeneratedCommentRead = _neuro_commenting_contracts.NeuroGeneratedCommentRead
NeuroGeneratedCommentRejectRequest = _neuro_commenting_contracts.NeuroGeneratedCommentRejectRequest
NeuroGeneratedCommentUpdate = _neuro_commenting_contracts.NeuroGeneratedCommentUpdate
NeuroAcceptedJobRead = _neuro_commenting_contracts.NeuroAcceptedJobRead
NeuroGenerateObservedPostRequest = _neuro_commenting_contracts.NeuroGenerateObservedPostRequest
NeuroLimitCreate = _neuro_commenting_contracts.NeuroLimitCreate
NeuroLimitPageRead = _neuro_commenting_contracts.NeuroLimitPageRead
NeuroLimitRead = _neuro_commenting_contracts.NeuroLimitRead
NeuroLimitUpdate = _neuro_commenting_contracts.NeuroLimitUpdate
NeuroManualSendRead = _neuro_commenting_contracts.NeuroManualSendRead
NeuroManualSendRequest = _neuro_commenting_contracts.NeuroManualSendRequest
NeuroLiveReadinessCheckRead = _neuro_commenting_contracts.NeuroLiveReadinessCheckRead
NeuroLiveReadinessRead = _neuro_commenting_contracts.NeuroLiveReadinessRead
NeuroObservedPostPageRead = _neuro_commenting_contracts.NeuroObservedPostPageRead
NeuroObservedPostRead = _neuro_commenting_contracts.NeuroObservedPostRead
NeuroPromptPresetListRead = _neuro_commenting_contracts.NeuroPromptPresetListRead
NeuroPromptPresetRead = _neuro_commenting_contracts.NeuroPromptPresetRead
NeuroObserveCampaignRequest = _neuro_commenting_contracts.NeuroObserveCampaignRequest
NeuroObserveTargetRequest = _neuro_commenting_contracts.NeuroObserveTargetRequest
NeuroTargetBulkCreateItem = _neuro_commenting_contracts.NeuroTargetBulkCreateItem
NeuroTargetBulkCreateRead = _neuro_commenting_contracts.NeuroTargetBulkCreateRead
NeuroTargetBulkCreateRequest = _neuro_commenting_contracts.NeuroTargetBulkCreateRequest
NeuroTargetBulkSkippedItemRead = _neuro_commenting_contracts.NeuroTargetBulkSkippedItemRead
NeuroTargetCreate = _neuro_commenting_contracts.NeuroTargetCreate
NeuroTargetPageRead = _neuro_commenting_contracts.NeuroTargetPageRead
NeuroTargetRead = _neuro_commenting_contracts.NeuroTargetRead

WarmupCheckItemRead = _warmup_contracts.WarmupCheckItemRead
WarmupCheckSeverityRead = _warmup_contracts.WarmupCheckSeverityRead
WarmupEventPageRead = _warmup_contracts.WarmupEventPageRead
WarmupEventRead = _warmup_contracts.WarmupEventRead
WarmupExecutionModeRead = _warmup_contracts.WarmupExecutionModeRead
WarmupIsolationClaimRead = _warmup_contracts.WarmupIsolationClaimRead
WarmupIsolationStatusRead = _warmup_contracts.WarmupIsolationStatusRead
WarmupPauseRequest = _warmup_contracts.WarmupPauseRequest
WarmupPresetKindRead = _warmup_contracts.WarmupPresetKindRead
WarmupReadinessRead = _warmup_contracts.WarmupReadinessRead
WarmupSessionCreateRequest = _warmup_contracts.WarmupSessionCreateRequest
WarmupSessionPageRead = _warmup_contracts.WarmupSessionPageRead
WarmupSessionRead = _warmup_contracts.WarmupSessionRead
WarmupSessionStatusRead = _warmup_contracts.WarmupSessionStatusRead
WarmupSessionSummaryRead = _warmup_contracts.WarmupSessionSummaryRead
WarmupStatusRead = _warmup_contracts.WarmupStatusRead
WarmupStrategyRead = _warmup_contracts.WarmupStrategyRead
WarmupValidateRead = _warmup_contracts.WarmupValidateRead
WarmupValidateRequest = _warmup_contracts.WarmupValidateRequest

_ACCOUNT_EDITING_CONTRACT_NAMES = {
    "AccountUpdateCreate",
    "AccountUpdateJobSummaryRead",
    "AccountUpdatePreviewRead",
    "AccountUpdateProfileAudioDesiredState",
    "AccountUpdateProfileDesiredState",
    "AccountUpdateStoryDesiredState",
}

ProfileCooldownSeconds = Literal[0] | Annotated[int, Field(ge=30, le=600)]
OperationCooldownSeconds = Literal[0] | Annotated[int, Field(ge=30, le=86400)]


def __getattr__(name: str) -> object:
    if name not in _ACCOUNT_EDITING_CONTRACT_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from app.modules.account_editing import contracts as _account_editing_contracts

    value = getattr(_account_editing_contracts, name)
    globals()[name] = value
    return value


def _empty_readiness_risk_items() -> list[AccountReadinessRiskRead]:
    return []


def _empty_import_items() -> list[AccountImportItemRead]:
    return []


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class AccountCreate(BaseModel):
    external_ref: str = Field(min_length=1)
    telegram_user_id: str | None = Field(default=None, min_length=1)
    origin: Literal["imported", "bought", "created"] = "imported"


class AccountWarmupInfoRead(BaseModel):
    session_id: str | None = None
    status: str | None = None
    current_day: int | None = None
    is_locked: bool = False


class CurrentUserRead(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    workspace_id: str
    workspace_name: str
    role: str
    auth_source: str


class WorkspaceRead(BaseModel):
    id: str
    name: str
    slug: str
    owner_user_id: str
    status: str
    safety_pipeline_v2_enabled: bool
    notification_webhook_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class WorkspaceFeatureFlagsUpdate(BaseModel):
    safety_pipeline_v2_enabled: StrictBool

    model_config = ConfigDict(extra="forbid")


class WorkspaceNotificationSettingsUpdate(BaseModel):
    notification_webhook_url: str | None = Field(
        default=None,
        max_length=512,
        pattern=r"^https://",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("notification_webhook_url")
    @classmethod
    def _validate_https_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("https://"):
            raise ValueError("notification_webhook_url must be an HTTPS URL")
        return value


class AccountRead(BaseModel):
    id: str
    external_ref: str
    telegram_user_id: str | None
    auth_source: str
    origin: Literal["imported", "bought", "created"]
    account_state: str
    terminal_status: TerminalStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AccountListItemRead(BaseModel):
    account_id: str
    display_name: str | None
    username: str | None
    phone_number: str
    telegram_user_id: str | None
    origin: Literal["imported", "bought", "created"]
    account_state: str
    terminal_status: TerminalStatus
    runtime_health: str
    is_execution_usable: bool
    is_test_dc: bool
    profile_photo_asset_id: str | None
    updated_at: datetime
    warmup: AccountWarmupInfoRead | None = None


class RuntimeRefreshRead(BaseModel):
    account_id: str
    account_state: str
    runtime_health: str
    is_execution_usable: bool
    last_error_code: str | None
    last_error_class: str | None
    refreshed_at: datetime


class AccountRuntimeDiagnosticsRead(BaseModel):
    account_id: str
    account_state: str
    runtime_health: str
    reauth_required: bool
    authorized_last_confirmed_at: datetime | None
    can_start_profile_job: bool
    last_error_code: str | None
    last_error_class: str | None
    tdlib_configured: bool
    manual_intervention_required: bool
    recovery_marker: str | None
    lock_owner: str | None
    lock_epoch: int
    diagnostic_timestamp: str


class AccountReadinessRiskReasonRead(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str


class AccountReadinessRiskRead(BaseModel):
    account_id: str
    score: int
    level: Literal["low", "medium", "high", "critical"]
    reasons: list[AccountReadinessRiskReasonRead]
    recommended_action: str | None = None
    computed_at: datetime


class AccountReadinessRiskSummaryRead(BaseModel):
    total: int
    low: int
    medium: int
    high: int
    critical: int
    reauth_required: int
    missing_session: int
    runtime_unhealthy: int
    proxy_problem: int
    items: list[AccountReadinessRiskRead] = Field(default_factory=_empty_readiness_risk_items)
    computed_at: datetime


class SensitiveAuditEventRead(BaseModel):
    id: str
    workspace_id: str
    actor_user_id: str | None = None
    actor_type: str
    action: str
    entity_type: str
    entity_id: str | None = None
    account_id: str | None = None
    request_id: str | None = None
    reason: str | None = None
    override_reason: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SensitiveAuditEventPageRead(BaseModel):
    items: list[SensitiveAuditEventRead]
    total: int
    limit: int
    offset: int


class ActionGateRead(BaseModel):
    account_id: str
    action_type: str
    allowed: bool
    requires_override: bool
    blocked: bool
    risk_level: str
    risk_score: int
    reasons: list[AccountReadinessRiskReasonRead]
    required_override_reason: bool


class QueueDescriptorRead(BaseModel):
    name: str
    purpose: str
    live_execution_default: bool


class WorkerDiagnosticsRead(BaseModel):
    queues: list[QueueDescriptorRead]
    mode: str
    redis: dict[str, Any]
    scheduler: dict[str, Any]
    reaper: dict[str, Any]
    rate_limits: dict[str, int]
    tdlib: dict[str, Any]


class TdlibRuntimeStatusRead(BaseModel):
    configured: bool
    library_configured: bool
    library_loadable: bool
    live_enabled: bool
    runtime_mode: str
    api_id_configured: bool
    api_hash_configured: bool
    readonly_smoke_available: bool
    error_code: str | None = None


class TelegramAuthSessionCreate(BaseModel):
    phone_number: str = Field(min_length=3, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    proxy_id: str | None = None


class TelegramAuthCodeSubmit(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class TelegramAuthPasswordSubmit(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TelegramAuthSessionRead(BaseModel):
    id: str
    workspace_id: str
    account_id: str | None
    phone_hint: str | None
    label: str | None
    status: str
    source: str
    requires_code: bool
    requires_password: bool
    cooldown_until: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None

    @field_serializer("cooldown_until", "created_at", "updated_at", "completed_at", "failed_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AccountImportBatchCreate(BaseModel):
    source_type: Literal["tdlib-directory", "tdata", "session-file", "json-metadata"]
    label: str | None = Field(default=None, max_length=255)
    dry_run: StrictBool = True
    metadata: dict[str, Any] | None = None


class AccountImportBatchValidate(BaseModel):
    metadata: dict[str, Any] | None = None
    content_base64: str | None = Field(
        default=None,
        pattern=r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",
    )


class AccountImportBatchConfirm(BaseModel):
    confirmation: Literal["IMPORT"]


class AccountImportItemRead(BaseModel):
    id: str
    account_id: str | None
    status: str
    phone_hint: str | None
    username_hint: str | None
    validation_code: str | None
    validation_message: str | None
    risk_level: str | None
    created_at: datetime
    updated_at: datetime


class AccountImportBatchRead(BaseModel):
    id: str
    workspace_id: str
    source_type: str
    status: str
    label: str | None
    dry_run: bool
    item_count: int
    created_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    items: list[AccountImportItemRead] = Field(default_factory=_empty_import_items)


class RetryPolicyRead(BaseModel):
    retry: bool
    max_attempts: int
    interval_seconds: list[int]
    failure_ttl_seconds: int
    result_ttl_seconds: int
    error_category: str


class AccountValidityCheckRequest(BaseModel):
    mode: Literal["db_snapshot", "tdlib_readonly", "full_capability"] = "db_snapshot"


class AccountBatchSafetyPreviewRequest(BaseModel):
    account_ids: list[str] = Field(min_length=1, max_length=500)
    operation: str = "batch_operation"
    allow_warning_overrides: bool = False


class AccountBatchSafetyItemRead(BaseModel):
    account_id: str
    batch_status: str
    health_status: str
    risk_level: str
    reasons: list[AccountSafetyReasonRead]
    cooldowns: list[AccountOperationCooldownRead]


class AccountBatchSafetyPreviewRead(BaseModel):
    operation: str
    can_start: bool
    counts: dict[str, int]
    blocking_account_ids: list[str]
    warning_account_ids: list[str]
    items: list[AccountBatchSafetyItemRead]


class AccountSafetyOverrideCreate(BaseModel):
    operation: str
    reason: str = Field(min_length=3, max_length=1000)
    requested_blockers: list[str] = Field(default_factory=list)


class AccountSafetyOverrideRead(BaseModel):
    id: str
    account_id: str
    operation: str
    reason: str
    requested_blockers: list[str]
    allowed_until: datetime
    created_at: datetime


class AccountOperationLogRead(BaseModel):
    id: str
    account_id: str
    operation_type: str
    operation_key: str | None = None
    status: str
    severity: str
    source: str
    message: str
    error_code: str | None = None
    error_class: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    job_id: str | None = None
    step_id: str | None = None
    created_at: datetime


class AccountOperationLogPageRead(BaseModel):
    items: list[AccountOperationLogRead]
    total: int
    limit: int
    offset: int


class AccountProxyUpsert(BaseModel):
    proxy_type: Literal["socks5", "http"]
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=1000)


class AccountProxyRead(BaseModel):
    account_id: str
    proxy_type: str
    host: str
    port: int
    username: str | None = None
    has_password: bool
    status: str
    last_checked_at: datetime | None = None
    last_check_scope: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    tdlib_verified_at: datetime | None = None
    tdlib_last_error_code: str | None = None
    tdlib_last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AccountProxySummaryRead(BaseModel):
    account_id: str
    status: str
    proxy_type: str | None = None
    host: str | None = None
    port: int | None = None
    last_checked_at: datetime | None = None
    last_check_scope: str | None = None
    last_error_code: str | None = None
    tdlib_verified_at: datetime | None = None
    tdlib_last_error_code: str | None = None


class FieldErrorRead(BaseModel):
    field: str
    message: str


class ApiErrorRead(BaseModel):
    error_code: str
    error_class: str
    message: str
    details: dict[str, Any] | None
    field_errors: list[FieldErrorRead]
    request_id: str


class DiagnosticsRead(BaseModel):
    database: str
    redis: str
    tdlib: str


class ReadinessRead(BaseModel):
    status: str


class FrontendDiagnosticsDatabaseRead(BaseModel):
    status: str
    mode: str


class FrontendDiagnosticsRedisRead(BaseModel):
    status: str
    configured: bool


class FrontendDiagnosticsStorageRead(BaseModel):
    backend: str
    bucket_configured: bool
    signed_url_enabled: bool
    public_base_url_configured: bool


class FrontendDiagnosticsTdlibRead(BaseModel):
    status: str
    profile_execution_adapter: str
    live_enabled: bool
    runtime_mode: str = "mock"
    library_configured: bool = False
    library_loadable: bool = False
    api_id_configured: bool = False
    api_hash_configured: bool = False
    auth_worker_ready: bool = False
    readonly_smoke_available: bool = False
    session_root_configured: bool = False
    execution_plane_ready: bool = False
    error_code: str | None = None


class FrontendDiagnosticsWorkersRead(BaseModel):
    queues: list[str]
    mode: str
    scheduler_enabled: bool = False
    reaper_mode: str = "dry_run"


class FrontendDiagnosticsSummaryRead(BaseModel):
    app_env: str
    auth_mode: str
    db: FrontendDiagnosticsDatabaseRead
    redis: FrontendDiagnosticsRedisRead
    storage: FrontendDiagnosticsStorageRead
    tdlib: FrontendDiagnosticsTdlibRead
    workers: FrontendDiagnosticsWorkersRead
    generated_at: datetime


class ExecutionPolicyRead(BaseModel):
    profile_job_cooldown_seconds: int
    profile_job_cooldown_enabled: bool
    allowed_profile_job_cooldown_seconds: list[int]
    profile_update_cooldown_seconds: int
    username_cooldown_seconds: int
    profile_photo_cooldown_seconds: int
    profile_music_cooldown_seconds: int
    story_post_cooldown_seconds: int
    story_delete_cooldown_seconds: int
    unknown_capability_policy: str
    recent_failure_policy: str
    fresh_validity_required: str
    fresh_validity_max_age_minutes: int
    manual_hard_blocker_override_enabled: bool
    non_overridable_blockers: list[str]


class ExecutionPolicyUpdate(BaseModel):
    profile_job_cooldown_seconds: ProfileCooldownSeconds = Field(
        default=cast(ProfileCooldownSeconds, None)
    )
    profile_update_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    username_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    profile_photo_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    profile_music_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    story_post_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    story_delete_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    unknown_capability_policy: Literal["warning_only", "block_live_execution"] = Field(
        default=cast(Literal["warning_only", "block_live_execution"], None)
    )
    recent_failure_policy: Literal["warning_only", "cooldown"] = Field(
        default=cast(Literal["warning_only", "cooldown"], None)
    )
    fresh_validity_required: Literal["never", "if_stale", "always_for_live"] = Field(
        default=cast(Literal["never", "if_stale", "always_for_live"], None)
    )
    fresh_validity_max_age_minutes: Annotated[int, Field(ge=1, le=1440)] = Field(
        default=cast(int, None)
    )
    manual_hard_blocker_override_enabled: StrictBool = Field(default=cast(StrictBool, None))

    @field_validator(
        "profile_job_cooldown_seconds",
        "profile_update_cooldown_seconds",
        "username_cooldown_seconds",
        "profile_photo_cooldown_seconds",
        "profile_music_cooldown_seconds",
        "story_post_cooldown_seconds",
        "story_delete_cooldown_seconds",
        "fresh_validity_max_age_minutes",
        mode="before",
    )
    @classmethod
    def _reject_boolean_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid integers")
        return value


class LivePreflightRead(BaseModel):
    tdjson_present: bool
    tdlib_credentials_present: bool
    postgres_reachable: bool
    redis_reachable: bool
    storage_writable: bool
    rq_worker_expected: bool
    rq_worker_status: str | None = None
    profile_worker_status: str | None = None
    auth_worker_status: str | None = None
    overall_status: str


class OtpStartRequest(BaseModel):
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class OtpConfirmRequest(BaseModel):
    account_id: str
    code: str


class PasswordSubmitRequest(BaseModel):
    account_id: str
    password: str


class AuthStateRead(BaseModel):
    account_id: str
    external_ref: str
    telegram_user_id: str | None
    orchestration_state: str
    auth_step_status: str
    needs_code: bool
    needs_password: bool = False
    password_hint: str | None = None
    session_present: bool
    runtime_health: str
    reauth_required: bool
    recovery_marker: str | None
    authorized_last_confirmed_at: datetime | None
    error: str | None = None


class AuthRuntimeModeRead(BaseModel):
    tdlib_use_test_dc: bool
    tdlib_production_auth_enabled: bool


class AuthRuntimeModeUpdate(BaseModel):
    tdlib_use_test_dc: StrictBool


class AuthBatchPhoneInput(BaseModel):
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    label: str | None = None


class AuthBatchValidatePhoneInput(BaseModel):
    phone_number: str = Field(min_length=1)
    label: str | None = None


class AuthBatchValidateRequest(BaseModel):
    items: list[AuthBatchValidatePhoneInput] = Field(min_length=1)


class AuthBatchValidItemRead(BaseModel):
    phone_number: str
    label: str | None = None
    position: int


class AuthBatchInvalidItemRead(BaseModel):
    input: str
    label: str | None = None
    position: int
    error: str


class AuthBatchPhoneConflictRead(BaseModel):
    phone_number: str
    label: str | None = None
    position: int
    account_id: str | None = None
    batch_item_id: str | None = None
    batch_id: str | None = None


class AuthBatchValidateRead(BaseModel):
    valid_items: list[AuthBatchValidItemRead]
    invalid_items: list[AuthBatchInvalidItemRead]
    duplicates: list[AuthBatchPhoneConflictRead]
    existing_accounts: list[AuthBatchPhoneConflictRead]
    active_batch_conflicts: list[AuthBatchPhoneConflictRead]


class AuthBatchCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    label: str | None = None
    items: list[AuthBatchPhoneInput] = Field(min_length=1)
    max_running_commands: int = Field(default=2, ge=1, le=12)
    max_waiting_input: int = Field(default=5, ge=1, le=12)
    max_total_active: int = Field(default=6, ge=1, le=12)

    @field_validator("max_running_commands", "max_waiting_input", "max_total_active", mode="before")
    @classmethod
    def _reject_boolean_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid integers")
        return value


class AuthBatchRead(BaseModel):
    id: str
    label: str | None
    status: str
    total_count: int
    success_count: int
    failed_count: int
    cancelled_count: int
    skipped_count: int
    max_running_commands: int
    max_waiting_input: int
    max_total_active: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_serializer("created_at", "started_at", "finished_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AuthBatchItemRead(BaseModel):
    id: str
    batch_id: str
    account_id: str
    phone_number: str | None
    phone_hint: str
    label: str | None
    position: int
    status: str
    attempt_count: int
    resend_count: int
    code_error_count: int
    password_error_count: int
    code_expires_at: datetime | None
    next_retry_at: datetime | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    authorized_at: datetime | None

    @field_serializer("code_expires_at", "next_retry_at", "updated_at", "authorized_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AuthBatchSnapshotRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int

    @field_serializer("server_time")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AuthBatchPollRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int

    @field_serializer("server_time")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AuthBatchSubmitCodeRequest(BaseModel):
    code: str
    idempotency_key: str

    def __repr__(self) -> str:
        return f"AuthBatchSubmitCodeRequest(code=***REDACTED***, idempotency_key={self.idempotency_key!r})"


class AuthBatchSubmitPasswordRequest(BaseModel):
    password: str
    idempotency_key: str

    def __repr__(self) -> str:
        return f"AuthBatchSubmitPasswordRequest(password=***REDACTED***, idempotency_key={self.idempotency_key!r})"


class AuthBatchEventRead(BaseModel):
    id: str
    batch_id: str
    batch_item_id: str | None
    event_type: str
    actor: str
    payload_json: dict[str, Any]
    created_at: datetime


class AssetRead(BaseModel):
    id: str
    kind: str
    source_path: str
    normalized_path: str
    storage_backend: str | None = None
    storage_bucket: str | None = None
    source_key: str | None = None
    normalized_key: str | None = None
    source_size_bytes: int | None = None
    normalized_size_bytes: int | None = None
    source_content_type: str | None = None
    normalized_content_type: str | None = None
    source_checksum: str | None = None
    normalized_checksum: str | None = None
    storage_migrated_at: datetime | None = None
    original_filename: str | None = None
    content_hash: str
    mime: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileJobCreate(BaseModel):
    account_id: str
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None
    mock_fail_step: str | None = None
    mock_crash_after_step_started: str | None = None


class ProfilePreviewRequest(BaseModel):
    account_id: str
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None


class StoryDraftCreate(BaseModel):
    account_id: str
    asset_id: str
    media_kind: Literal["image", "video"]
    caption: str | None = None
    privacy_preset: str = "contacts"
    active_period_seconds: int = 86400
    protect_content: bool = False


class StoryDraftUpdate(BaseModel):
    caption: str | None = None
    privacy_preset: str | None = None
    active_period_seconds: int | None = None
    protect_content: bool | None = None


class StoryDraftRead(BaseModel):
    id: str
    account_id: str
    asset_id: str
    media_kind: str
    caption: str | None
    privacy_preset: str
    active_period_seconds: int
    protect_content: bool
    validation_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoryCapabilitiesRead(BaseModel):
    account_id: str
    stories_enabled: bool
    tdlib_live_publishing_enabled: bool
    can_prepare_image: bool
    can_prepare_video: bool
    allowed_active_period_seconds: list[int]
    allowed_privacy_presets: list[str]
    max_caption_length: int
    ffprobe_available: bool
    ffmpeg_available: bool
    warnings: list[str]


class DashboardAccountRead(BaseModel):
    account_id: str
    display_name: str | None
    username: str | None
    phone_number: str | None
    telegram_user_id: str | None
    account_state: str
    runtime_health: str
    reauth_required: bool
    is_execution_usable: bool


class DashboardCurrentProfileRead(BaseModel):
    first_name: str | None
    last_name: str | None
    bio: str | None
    username: str | None
    profile_photo_asset_id: str | None


class DashboardEditableFieldsRead(BaseModel):
    name: str | None
    bio: str | None
    username: str | None
    profile_photo: str | None


class DashboardProfileAudioRead(BaseModel):
    telegram_file_id: str | None
    title: str | None
    performer: str | None
    duration_seconds: int | None
    mime: str | None
    source_asset_id: str | None


class DashboardStoryPostRead(BaseModel):
    id: str
    story_poster_chat_id: str | None
    telegram_story_id: str | None
    temporary_story_id: str | None
    media_kind: str
    asset_id: str | None
    caption: str | None
    privacy_preset: str
    active_period_seconds: int
    protect_content: bool
    can_be_deleted: bool
    status: str
    failure_code: str | None
    failure_message: str | None
    posted_at: datetime | None
    expires_at: datetime | None


class DashboardPipelineRead(BaseModel):
    latest_job: JobSummaryRead | None
    latest_job_state: str | None
    latest_job_id: str | None
    latest_job_finished_at: datetime | None
    has_active_job: bool
    unsaved_changes_supported: bool


class DashboardDiagnosticsRead(BaseModel):
    last_error_code: str | None
    last_error_class: str | None
    authorized_last_confirmed_at: datetime | None
    real_execution_enabled: bool = False
    stories_live_execution_enabled: bool = False


class DashboardProfileRead(BaseModel):
    account: DashboardAccountRead
    current_profile: DashboardCurrentProfileRead
    profile_audio: DashboardProfileAudioRead | None
    story_posts: list[DashboardStoryPostRead]
    editable_fields: DashboardEditableFieldsRead
    pipeline: DashboardPipelineRead
    diagnostics: DashboardDiagnosticsRead


class JobRead(BaseModel):
    id: str
    account_id: str
    job_state: str
    execution_intent_hash: str
    job_payload_version: int
    payload_json: dict[str, Any]
    plan_json_snapshot: dict[str, Any]
    dedup_blocked_by_job_id: str | None
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class JobStepResultRead(BaseModel):
    id: str
    job_id: str
    step_key: str
    step_type: str
    status: str
    attempt_no: int
    uncertain_reason: str | None
    verification_attempted: bool
    verification_result: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_class: str | None
    result_payload_json: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class JobDetailRead(BaseModel):
    job_id: str
    job_state: str
    account_id: str
    execution_intent_hash: str
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None
    can_retry: bool
    can_refresh_runtime: bool
    step_counts: dict[str, int]


class JobStepListItemRead(BaseModel):
    step_key: str
    step_type: str
    status: str
    verification_attempted: bool
    verification_result: dict[str, Any] | None
    uncertain_reason: str | None
    error_code: str | None
    error_class: str | None
    result_payload_json: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None
