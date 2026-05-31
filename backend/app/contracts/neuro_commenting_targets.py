from __future__ import annotations

from typing import Literal

from app.contracts.neuro_commenting_common import (
    BaseModel,
    ConfigDict,
    Field,
    _empty_keywords,
    _serialize_utc_datetime,
    datetime,
    field_serializer,
)

class NeuroTargetCreate(BaseModel):
    channel_ref: str = Field(min_length=1, max_length=255)
    channel_id: str | None = None
    discussion_chat_id: str | None = None
    title: str | None = None
    username: str | None = None
    source_type: str = "channel"
    activity_level: str | None = None
    keywords: list[str] = Field(default_factory=_empty_keywords)
    exclude_keywords: list[str] = Field(default_factory=_empty_keywords)

    model_config = ConfigDict(extra="forbid")


class NeuroTargetRead(BaseModel):
    id: str
    campaign_id: str
    channel_ref: str
    channel_id: str | None
    discussion_chat_id: str | None
    title: str | None
    username: str | None
    status: str
    source_type: str
    activity_level: str | None
    keywords: list[str]
    exclude_keywords: list[str]
    last_seen_message_id: str | None
    last_processed_message_id: str | None
    last_commented_at: datetime | None
    health_score: float
    success_count: int
    fail_count: int
    deleted_comment_count: int
    flood_wait_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_commented_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroTargetPageRead(BaseModel):
    items: list[NeuroTargetRead]
    total: int
    page: int
    limit: int


class NeuroTargetBulkCreateItem(NeuroTargetCreate):
    """Single item in a bulk-import request - shares the create contract."""

    model_config = ConfigDict(extra="forbid")


class NeuroTargetBulkCreateRequest(BaseModel):
    items: list[NeuroTargetBulkCreateItem] = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")


class NeuroTargetBulkSkippedItemRead(BaseModel):
    channel_ref: str
    reason: Literal["duplicate", "blacklisted_workspace", "invalid_ref", "limit_exceeded"]


class NeuroTargetBulkCreateRead(BaseModel):
    created: list[NeuroTargetRead]
    skipped: list[NeuroTargetBulkSkippedItemRead]
    requested: int
