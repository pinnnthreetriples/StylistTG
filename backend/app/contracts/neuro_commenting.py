from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator

PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
DelayMaxInt = Annotated[int, Field(ge=60)]
CampaignMode = Literal["all_posts", "keyword_match", "random_posts", "semantic_match"]
WorkMode = Literal["by_comment_count", "by_time_window", "manual", "scheduled"]
ApprovalMode = Literal["manual_required", "trusted_auto", "auto"]
SendMode = Literal["dry_run", "manual_approval", "semi_auto"]
SendStrategy = Literal["comment"]
RotationStrategy = Literal["round_robin", "weighted", "least_used", "random"]
AutoSendDisabled = Literal[False]
LimitScopeType = Literal[
    "workspace", "campaign", "account", "target", "campaign_account", "campaign_target"
]
LimitType = Literal[
    "comments_per_minute",
    "comments_per_hour",
    "comments_per_day",
    "min_delay_between_comments",
    "max_parallel_attempts",
]
ChannelRuleType = Literal[
    "blacklist", "whitelist", "auto_blacklist_suggested", "auto_whitelist_suggested"
]

# Phase 0 Task 1: enum values declared in DB/python enum but not yet implemented.
# Reject at Create/Update boundary with feature_not_available marker.
_DISABLED_CAMPAIGN_MODES: frozenset[str] = frozenset({"semantic_match"})
_DISABLED_WORK_MODES: frozenset[str] = frozenset({"scheduled"})
_DISABLED_CHANNEL_RULE_TYPES: frozenset[str] = frozenset(
    {"auto_blacklist_suggested", "auto_whitelist_suggested"}
)


def _reject_disabled_value(value: object, *, disabled: frozenset[str], feature: str) -> object:
    if isinstance(value, str) and value in disabled:
        raise ValueError(f"feature_not_available: {feature}={value}")
    return value


def _serialize_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


def _empty_keywords() -> list[str]:
    return []


class NeuroCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    mode: CampaignMode = "all_posts"
    work_mode: WorkMode = "manual"
    approval_mode: ApprovalMode = "manual_required"
    send_mode: SendMode = "dry_run"
    send_strategy: SendStrategy = "comment"
    rotation_strategy: RotationStrategy = "round_robin"
    language_mode: str = "auto"
    prompt_template: str | None = None
    system_prompt: str | None = None
    negative_prompt: str | None = None
    max_comments_total: PositiveInt | None = None
    max_comments_per_hour: PositiveInt | None = None
    max_comments_per_day: PositiveInt | None = None
    delay_min_seconds: NonNegativeInt = 60
    delay_max_seconds: DelayMaxInt = 300
    rotate_after_comments: PositiveInt | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    dry_run: StrictBool = True
    auto_send_enabled: AutoSendDisabled = False
    safety_enabled: StrictBool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "max_comments_total",
        "max_comments_per_hour",
        "max_comments_per_day",
        "delay_min_seconds",
        "delay_max_seconds",
        "rotate_after_comments",
        mode="before",
    )
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value

    @field_validator("auto_send_enabled", mode="before")
    @classmethod
    def _reject_enabled_auto_send(cls, value: object) -> object:
        if value is not False:
            raise ValueError("auto_send_enabled must be false")
        return value

    @field_validator("mode", mode="before")
    @classmethod
    def _reject_disabled_mode(cls, value: object) -> object:
        return _reject_disabled_value(value, disabled=_DISABLED_CAMPAIGN_MODES, feature="mode")

    @field_validator("work_mode", mode="before")
    @classmethod
    def _reject_disabled_work_mode(cls, value: object) -> object:
        return _reject_disabled_value(
            value, disabled=_DISABLED_WORK_MODES, feature="work_mode"
        )


class NeuroCampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    mode: CampaignMode | None = None
    work_mode: WorkMode | None = None
    approval_mode: ApprovalMode | None = None
    send_mode: SendMode | None = None
    send_strategy: SendStrategy | None = None
    rotation_strategy: RotationStrategy | None = None
    language_mode: str | None = None
    prompt_template: str | None = None
    system_prompt: str | None = None
    negative_prompt: str | None = None
    max_comments_total: PositiveInt | None = None
    max_comments_per_hour: PositiveInt | None = None
    max_comments_per_day: PositiveInt | None = None
    delay_min_seconds: NonNegativeInt | None = None
    delay_max_seconds: DelayMaxInt | None = None
    rotate_after_comments: PositiveInt | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    dry_run: StrictBool | None = None
    auto_send_enabled: AutoSendDisabled | None = None
    safety_enabled: StrictBool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "max_comments_total",
        "max_comments_per_hour",
        "max_comments_per_day",
        "delay_min_seconds",
        "delay_max_seconds",
        "rotate_after_comments",
        mode="before",
    )
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value

    @field_validator("auto_send_enabled", mode="before")
    @classmethod
    def _reject_enabled_auto_send(cls, value: object) -> object:
        if value is not None and value is not False:
            raise ValueError("auto_send_enabled must be false")
        return value

    @field_validator("mode", mode="before")
    @classmethod
    def _reject_disabled_mode(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_disabled_value(value, disabled=_DISABLED_CAMPAIGN_MODES, feature="mode")

    @field_validator("work_mode", mode="before")
    @classmethod
    def _reject_disabled_work_mode(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_disabled_value(
            value, disabled=_DISABLED_WORK_MODES, feature="work_mode"
        )


class NeuroCampaignRead(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    status: str
    mode: str
    work_mode: str
    approval_mode: str
    send_mode: str
    send_strategy: str
    rotation_strategy: str
    language_mode: str
    prompt_template: str | None
    system_prompt: str | None
    negative_prompt: str | None
    prompt_version: int
    max_comments_total: int | None
    max_comments_per_hour: int | None
    max_comments_per_day: int | None
    delay_min_seconds: int
    delay_max_seconds: int
    rotate_after_comments: int | None
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    timezone: str | None
    dry_run: bool
    auto_send_enabled: bool
    safety_enabled: bool
    started_at: datetime | None
    stopped_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "stopped_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroCampaignPageRead(BaseModel):
    items: list[NeuroCampaignRead]
    total: int
    page: int
    limit: int


class NeuroCampaignAccountCreate(BaseModel):
    account_id: str
    rotation_weight: PositiveInt = 1
    rotation_order: NonNegativeInt = 0

    model_config = ConfigDict(extra="forbid")

    @field_validator("rotation_weight", "rotation_order", mode="before")
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value


class NeuroCampaignAccountRead(BaseModel):
    id: str
    campaign_id: str
    account_id: str
    status: str
    rotation_weight: int
    rotation_order: int
    comments_sent: int
    comments_failed: int
    last_used_at: datetime | None
    cooldown_until: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_used_at", "cooldown_until", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class NeuroCampaignAccountPageRead(BaseModel):
    items: list[NeuroCampaignAccountRead]
    total: int
    page: int
    limit: int


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

    @field_validator("rule_type", mode="before")
    @classmethod
    def _reject_disabled_rule_type(cls, value: object) -> object:
        return _reject_disabled_value(
            value, disabled=_DISABLED_CHANNEL_RULE_TYPES, feature="rule_type"
        )


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
