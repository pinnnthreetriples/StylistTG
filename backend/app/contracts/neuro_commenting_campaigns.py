from __future__ import annotations

from app.contracts.neuro_commenting_common import (
    ApprovalMode,
    AutoSendDisabled,
    BaseModel,
    CampaignMode,
    ConfigDict,
    DelayMaxInt,
    Field,
    NonNegativeInt,
    PositiveInt,
    RotationStrategy,
    SafetyPreset,
    SendMode,
    SendStrategy,
    StrictBool,
    WorkMode,
    _DISABLED_CAMPAIGN_MODES,
    _DISABLED_WORK_MODES,
    _reject_disabled_value,
    _serialize_utc_datetime,
    datetime,
    field_serializer,
    field_validator,
)

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
    safety_preset: SafetyPreset = "balanced"

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
        return _reject_disabled_value(value, disabled=_DISABLED_WORK_MODES, feature="work_mode")


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
    safety_preset: SafetyPreset | None = None

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
        return _reject_disabled_value(value, disabled=_DISABLED_WORK_MODES, feature="work_mode")


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
    safety_preset: str
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
