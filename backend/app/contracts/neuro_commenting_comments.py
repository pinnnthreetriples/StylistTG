from __future__ import annotations

from app.contracts.neuro_commenting_common import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    _serialize_utc_datetime,
    datetime,
    field_serializer,
)


class NeuroGeneratedCommentUpdate(BaseModel):
    edited_text: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class NeuroGeneratedCommentRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class NeuroGeneratedCommentRead(BaseModel):
    id: str
    campaign_id: str
    target_id: str | None
    account_id: str | None
    observed_post_id: str | None
    generated_text: str
    edited_text: str | None
    final_text: str | None
    model: str | None
    provider: str | None
    prompt_version: int
    language: str | None
    safety_status: str
    safety_reason: str | None
    approval_status: str
    approved_by: str | None
    approved_at: datetime | None
    rejected_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("approved_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroGeneratedCommentPageRead(BaseModel):
    items: list[NeuroGeneratedCommentRead]
    total: int
    page: int
    limit: int


class NeuroObservedPostRead(BaseModel):
    id: str
    campaign_id: str
    target_id: str
    source_chat_id: str
    source_message_id: str
    discussion_chat_id: str | None
    discussion_message_id: str | None
    discussion_resolved_at: datetime | None
    discussion_resolution_error_code: str | None
    post_text: str | None
    media_summary: str | None
    language: str | None
    matched_mode: str | None
    matched_keywords: list[str]
    status: str
    seen_at: datetime
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "discussion_resolved_at", "seen_at", "processed_at", "created_at", "updated_at"
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class NeuroObservedPostPageRead(BaseModel):
    items: list[NeuroObservedPostRead]
    total: int
    page: int
    limit: int


class NeuroObserveCampaignRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)
    generate: StrictBool = True

    model_config = ConfigDict(extra="forbid")


class NeuroObserveTargetRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)
    generate: StrictBool = True

    model_config = ConfigDict(extra="forbid")


class NeuroGenerateObservedPostRequest(BaseModel):
    force: StrictBool = False

    model_config = ConfigDict(extra="forbid")


class NeuroAttemptRead(BaseModel):
    id: str
    campaign_id: str
    generated_comment_id: str
    account_id: str | None
    target_id: str | None
    observed_post_id: str | None
    status: str
    send_strategy: str
    telegram_message_id: str | None
    error_code: str | None
    error_message: str | None
    flood_wait_seconds: int | None
    reserved_limit_at: datetime | None
    sent_at: datetime | None
    failed_at: datetime | None
    idempotency_key: str | None = None
    external_message_id_provisional: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("reserved_limit_at", "sent_at", "failed_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroAttemptPageRead(BaseModel):
    items: list[NeuroAttemptRead]
    total: int
    page: int
    limit: int


class NeuroManualSendRequest(BaseModel):
    enqueue: StrictBool = True

    model_config = ConfigDict(extra="forbid")


class NeuroManualSendRead(BaseModel):
    accepted: bool
    attempt: NeuroAttemptRead
    job_id: str | None = None
    queue_name: str | None = None
    send_enabled: bool
    disabled_reason: str | None = None


class NeuroAcceptedJobRead(BaseModel):
    accepted: bool
    job_id: str
    queue_name: str
