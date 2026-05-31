from __future__ import annotations

from typing import Literal

from app.contracts.neuro_commenting_common import (
    Any,
    BaseModel,
    ChannelRuleType,
    ConfigDict,
    Field,
    LimitScopeType,
    LimitType,
    PositiveInt,
    StrictBool,
    _serialize_utc_datetime,
    datetime,
    field_serializer,
    field_validator,
)

class NeuroEventRead(BaseModel):
    id: str
    workspace_id: str
    campaign_id: str | None
    account_id: str | None
    target_id: str | None
    observed_post_id: str | None
    generated_comment_id: str | None
    attempt_id: str | None
    event_type: str
    event_level: str
    message: str
    data_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _serialize_datetime(self, value: datetime) -> str:
        serialized = _serialize_utc_datetime(value)
        assert serialized is not None
        return serialized


class NeuroEventPageRead(BaseModel):
    items: list[NeuroEventRead]
    total: int
    page: int
    limit: int


class NeuroLiveReadinessCheckRead(BaseModel):
    code: str
    severity: Literal["info", "warning", "blocker"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class NeuroLiveReadinessRead(BaseModel):
    campaign_id: str
    ready: bool
    checks: list[NeuroLiveReadinessCheckRead]


class NeuroLimitRead(BaseModel):
    id: str
    campaign_id: str
    scope_type: str
    scope_id: str | None
    limit_type: str
    max_value: int
    window_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        serialized = _serialize_utc_datetime(value)
        assert serialized is not None
        return serialized


class NeuroLimitPageRead(BaseModel):
    items: list[NeuroLimitRead]
    total: int
    page: int
    limit: int


class NeuroLimitCreate(BaseModel):
    scope_type: LimitScopeType
    scope_id: str | None = None
    limit_type: LimitType
    max_value: PositiveInt
    window_seconds: PositiveInt
    enabled: StrictBool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_value", "window_seconds", mode="before")
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value


class NeuroLimitUpdate(BaseModel):
    scope_type: LimitScopeType | None = None
    scope_id: str | None = None
    limit_type: LimitType | None = None
    max_value: PositiveInt | None = None
    window_seconds: PositiveInt | None = None
    enabled: StrictBool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_value", "window_seconds", mode="before")
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value


class NeuroChannelRuleRead(BaseModel):
    id: str
    workspace_id: str
    target_ref: str
    rule_type: str
    reason: str | None
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _serialize_datetime(self, value: datetime) -> str:
        serialized = _serialize_utc_datetime(value)
        assert serialized is not None
        return serialized


class NeuroChannelRulePageRead(BaseModel):
    items: list[NeuroChannelRuleRead]
    total: int
    page: int
    limit: int


class NeuroChannelRuleCreate(BaseModel):
    target_ref: str = Field(min_length=1, max_length=255)
    rule_type: ChannelRuleType
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("target_ref")
    @classmethod
    def _target_ref_non_blank(cls, value: str) -> str:
        target_ref = value.strip()
        if not target_ref:
            raise ValueError("target_ref is required")
        return target_ref


class NeuroCampaignStatsRead(BaseModel):
    campaign_id: str
    posts_seen: int
    comments_generated: int
    comments_pending: int
    comments_edited: int
    comments_approved: int
    comments_rejected: int
    comments_sent: int
    comments_failed: int
    comments_skipped: int
    flood_wait_count: int
    success_rate: float
    approval_rate: float
    generation_rate: float
    last_observed_at: datetime | None
    last_generated_at: datetime | None
    last_sent_at: datetime | None

    @field_serializer("last_observed_at", "last_generated_at", "last_sent_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroAccountStatsRead(BaseModel):
    account_id: str
    comments_generated: int
    comments_sent: int
    comments_failed: int
    flood_wait_count: int
    success_rate: float
    last_success_at: datetime | None
    last_failure_at: datetime | None
    cooldown_until: datetime | None
    status: str | None

    @field_serializer("last_success_at", "last_failure_at", "cooldown_until")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroAccountStatsPageRead(BaseModel):
    items: list[NeuroAccountStatsRead]
    total: int
    page: int
    limit: int


class NeuroChannelStatsRead(BaseModel):
    target_id: str
    channel_ref: str
    title: str | None
    posts_seen: int
    comments_generated: int
    comments_sent: int
    comments_failed: int
    flood_wait_count: int
    health_score: float
    success_rate: float
    last_success_at: datetime | None
    last_failure_at: datetime | None
    rule_status: str

    @field_serializer("last_success_at", "last_failure_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroChannelStatsPageRead(BaseModel):
    items: list[NeuroChannelStatsRead]
    total: int
    page: int
    limit: int


class NeuroFailureReasonRead(BaseModel):
    error_code: str
    count: int
    last_seen_at: datetime | None

    @field_serializer("last_seen_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroFailureReasonPageRead(BaseModel):
    items: list[NeuroFailureReasonRead]
    total: int
    page: int
    limit: int


class NeuroPromptPresetRead(BaseModel):
    id: str
    name: str
    language: str
    description: str
    system_prompt: str
    prompt_template: str


class NeuroPromptPresetListRead(BaseModel):
    items: list[NeuroPromptPresetRead]
    total: int
