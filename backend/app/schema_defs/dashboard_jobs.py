from __future__ import annotations

# ruff: noqa: F403,F405

from app.schemas import *

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
