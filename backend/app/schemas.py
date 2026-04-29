from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    external_ref: str
    telegram_user_id: str | None = None


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


class ExecutionPolicyRead(BaseModel):
    profile_job_cooldown_seconds: int
    profile_job_cooldown_enabled: bool
    allowed_profile_job_cooldown_seconds: list[int]


class ExecutionPolicyUpdate(BaseModel):
    profile_job_cooldown_seconds: int


class LivePreflightRead(BaseModel):
    tdjson_present: bool
    tdlib_credentials_present: bool
    postgres_reachable: bool
    redis_reachable: bool
    storage_writable: bool
    rq_worker_expected: bool
    rq_worker_status: str | None = None
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
    phone_number: str
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
    stories: list[AccountUpdateStoryDesiredState] = []


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
