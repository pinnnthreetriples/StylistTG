from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.warmup import contracts as _warmup_contracts

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


def _empty_operation_cooldowns() -> list[AccountOperationCooldownRead]:
    return []


def _empty_readiness_risk_items() -> list[AccountReadinessRiskRead]:
    return []


def _empty_import_items() -> list[AccountImportItemRead]:
    return []


def _empty_update_stories() -> list[AccountUpdateStoryDesiredState]:
    return []


def _empty_operation_safety_items() -> list[AccountOperationSafetyRead]:
    return []


class AccountCreate(BaseModel):
    external_ref: str
    telegram_user_id: str | None = None


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


class AccountRead(BaseModel):
    id: str
    external_ref: str
    telegram_user_id: str | None
    auth_source: str
    account_state: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountListItemRead(BaseModel):
    account_id: str
    display_name: str | None
    username: str | None
    phone_number: str
    telegram_user_id: str | None
    account_state: str
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


class AccountSafetyReasonRead(BaseModel):
    code: str
    severity: str
    source: str
    message: str
    last_seen_at: datetime | None = None


class AccountCapabilityRead(BaseModel):
    state: str
    reason_codes: list[str]
    label: str
    last_checked_at: datetime | None = None
    source: str


class AccountRiskRead(BaseModel):
    level: str
    reasons: list[AccountSafetyReasonRead]


class AccountOperationCooldownRead(BaseModel):
    id: str
    account_id: str
    operation: str
    level: str
    reason_code: str
    started_at: datetime
    retry_after_at: datetime
    source: str
    source_job_id: str | None = None
    source_step_id: str | None = None


class AccountSafetySummaryRead(BaseModel):
    account_id: str
    health_status: str
    overall_risk_level: str
    validity_status: str
    proxy_status: str = "none"
    capability_summary: dict[str, str]
    cooldown_summary: list[AccountOperationCooldownRead] = Field(
        default_factory=_empty_operation_cooldowns
    )
    top_reasons: list[AccountSafetyReasonRead]
    last_checked_at: datetime
    source: str


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


class AccountDeletionPlannedActionRead(BaseModel):
    type: str
    resource: str
    count: int | None = None
    present: bool | None = None
    retention_policy: str | None = None


class AccountDeletionPreviewRead(BaseModel):
    account_id: str
    can_delete: bool
    risk_level: str
    risk_score: int
    blocking_reasons: list[str]
    planned_actions: list[AccountDeletionPlannedActionRead]
    requires_confirmation: bool
    generated_at: datetime


class AccountDeletionRequestCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)
    confirmation: Literal["DELETE"]
    dry_run: bool = True


class AccountDeletionRequestRead(BaseModel):
    id: str
    account_id: str
    status: str
    reason: str | None = None
    dry_run_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    requested_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class AccountExportRequestRead(BaseModel):
    id: str
    account_id: str
    status: str
    export_key: str | None = None
    export_size_bytes: int | None = None
    export_content_type: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    expires_at: datetime | None = None


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


class AccountImportBatchCreate(BaseModel):
    source_type: Literal["tdlib-directory", "tdata", "session-file", "json-metadata"]
    label: str | None = Field(default=None, max_length=255)
    dry_run: bool = True
    metadata: dict[str, Any] | None = None


class AccountImportBatchValidate(BaseModel):
    metadata: dict[str, Any] | None = None
    content_base64: str | None = None


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


class AccountOperationSafetyRead(BaseModel):
    operation: str
    state: str
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    cooldowns: list[AccountOperationCooldownRead] = Field(
        default_factory=_empty_operation_cooldowns
    )
    can_override: bool = False


class AccountValidityCheckRequest(BaseModel):
    mode: Literal["db_snapshot", "tdlib_readonly", "full_capability"] = "db_snapshot"


class AccountValidityCheckRead(BaseModel):
    id: str
    account_id: str
    mode: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_class: str | None
    details: dict[str, Any] | None
    result: dict[str, Any] | None
    created_at: datetime


class AccountSafetyRead(AccountSafetySummaryRead):
    capabilities: dict[str, AccountCapabilityRead]
    risk_by_operation: dict[str, AccountRiskRead]
    cooldowns_by_operation: dict[str, list[AccountOperationCooldownRead]]
    reasons: list[AccountSafetyReasonRead]
    last_validity_check: AccountValidityCheckRead | None = None


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
    profile_job_cooldown_seconds: int | None = None
    profile_update_cooldown_seconds: int | None = None
    username_cooldown_seconds: int | None = None
    profile_photo_cooldown_seconds: int | None = None
    profile_music_cooldown_seconds: int | None = None
    story_post_cooldown_seconds: int | None = None
    story_delete_cooldown_seconds: int | None = None
    unknown_capability_policy: Literal["warning_only", "block_live_execution"] | None = None
    recent_failure_policy: Literal["warning_only", "cooldown"] | None = None
    fresh_validity_required: Literal["never", "if_stale", "always_for_live"] | None = None
    fresh_validity_max_age_minutes: int | None = None
    manual_hard_blocker_override_enabled: bool | None = None


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
    phone_number: str


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
    tdlib_use_test_dc: bool


class AuthBatchPhoneInput(BaseModel):
    phone_number: str
    label: str | None = None


class AuthBatchValidateRequest(BaseModel):
    items: list[AuthBatchPhoneInput]


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
    idempotency_key: str
    label: str | None = None
    items: list[AuthBatchPhoneInput]
    max_running_commands: int = 2
    max_waiting_input: int = 5
    max_total_active: int = 6


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


class AuthBatchSnapshotRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int


class AuthBatchPollRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int


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


class ProfileAudioAction(StrEnum):
    KEEP = "keep"
    ADD = "add"
    REMOVE = "remove"


class AccountUpdateProfileDesiredState(BaseModel):
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None


class AccountUpdateProfileAudioDesiredState(BaseModel):
    action: ProfileAudioAction = ProfileAudioAction.KEEP
    audio_asset_id: str | None = None


class AccountUpdateStoryDesiredState(BaseModel):
    action: Literal["post_image", "post_video"]
    asset_id: str
    caption: str | None = None
    privacy_preset: str = "contacts"
    active_period_seconds: int = 86400
    protect_content: bool = False


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


class AccountUpdateCreate(BaseModel):
    account_id: str
    profile: AccountUpdateProfileDesiredState | None = None
    profile_audio: AccountUpdateProfileAudioDesiredState | None = None
    stories: list[AccountUpdateStoryDesiredState] = Field(default_factory=_empty_update_stories)


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


class JobSummaryRead(BaseModel):
    job_id: str
    job_state: str
    execution_intent_hash: str
    plan_summary: list[str]
    created_at: datetime | None
    dedup_blocked_by_job_id: str | None = None
    message: str | None = None


class AccountUpdateJobSummaryRead(JobSummaryRead):
    workflow_type: str
    workflow_version: int


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


class ProfilePreviewStepRead(BaseModel):
    step_key: str
    step_type: str
    order: int
    required: bool
    idempotency_class: str
    payload: dict[str, Any]


class ProfilePreviewRead(BaseModel):
    can_create_job: bool
    blocking_errors: list[str]
    warnings: list[str]
    normalized_payload: dict[str, Any]
    execution_intent_hash: str
    plan_json_snapshot: dict[str, Any]
    steps: list[ProfilePreviewStepRead]
    requires_execution_usable: bool
    dedup_would_block: bool
    dedup_blocked_by_job_id: str | None


class AccountUpdatePreviewRead(ProfilePreviewRead):
    workflow_type: str
    workflow_version: int
    desired_state_normalized: dict[str, Any]
    capability_snapshot: dict[str, str]
    account_safety: AccountSafetyRead | None = None
    risk_by_operation: dict[str, AccountRiskRead] = Field(default_factory=dict)
    cooldowns_by_operation: dict[str, list[AccountOperationCooldownRead]] = Field(
        default_factory=dict
    )
    safety_warnings: list[str] = Field(default_factory=list)
    safety_blockers: list[str] = Field(default_factory=list)
    operation_safety: list[AccountOperationSafetyRead] = Field(
        default_factory=_empty_operation_safety_items
    )


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
