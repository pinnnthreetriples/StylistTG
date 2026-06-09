from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.contracts.types import UuidString


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class WarmupStatusRead(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    SCHEDULED = "scheduled"
    COLD_SOAK = "cold_soak"
    ACTIVE = "active"
    PAUSED_RISK = "paused_risk"
    PAUSED_MANUAL = "paused_manual"
    COMPLETED = "completed"
    FAILED = "failed"


class WarmupCheckSeverityRead(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class WarmupEventSeverityRead(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class WarmupValidateRequest(BaseModel):
    account_id: UuidString
    strategy_id: UuidString


class WarmupProxyAdaptationRead(BaseModel):
    proxy_category: str
    applied_preset: Literal["economic", "balanced", "full"]
    disabled_actions: list[str] = Field(default_factory=list)


class WarmupCheckItemRead(BaseModel):
    key: str
    label: str
    passed: bool
    severity: WarmupCheckSeverityRead
    detail: str | None = None


class WarmupValidateRead(BaseModel):
    is_ready: bool
    checks: list[WarmupCheckItemRead]
    blocking_reasons: list[str]
    warnings: list[str]
    proxy_adaptation: WarmupProxyAdaptationRead | None = None


class WarmupSessionCreateRequest(BaseModel):
    account_id: UuidString
    strategy_id: UuidString


class WarmupCycleConfigRead(BaseModel):
    start_hour: int
    end_hour: int
    days_total: int
    current_cycle: int = 1
    started_at: str | None = None
    active_hours_total: int | None = None


class WarmupActionPresetRequest(BaseModel):
    preset: Literal["economic", "all", "minimal"]


class WarmupDisabledActionsRequest(BaseModel):
    actions: list[str] = Field(default_factory=list)


class WarmupBootstrapChannelCreate(BaseModel):
    channel_ref: str = Field(min_length=2, max_length=64, pattern=r"^@[A-Za-z0-9_]{1,63}$")
    category: Literal["news", "tech", "lifestyle", "sports", "entertainment", "business"]
    language: str = Field(min_length=2, max_length=16, pattern=r"^[A-Za-z][A-Za-z\-]{0,15}$")
    country: str | None = Field(default=None, max_length=8, pattern=r"^[A-Za-z]{2,8}$")

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("country")
    @classmethod
    def _normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class WarmupBootstrapChannelPatch(BaseModel):
    category: Literal["news", "tech", "lifestyle", "sports", "entertainment", "business"] | None = (
        None
    )
    language: str | None = Field(
        default=None, min_length=2, max_length=16, pattern=r"^[A-Za-z][A-Za-z\-]{0,15}$"
    )
    country: str | None = Field(default=None, max_length=8, pattern=r"^[A-Za-z]{2,8}$")
    is_active: bool | None = None

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("country")
    @classmethod
    def _normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class WarmupBootstrapChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel_ref: str
    category: str
    language: str
    country: str | None = None
    verified_safe_at: datetime
    added_by: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("verified_safe_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class WarmupActionMetadataRead(BaseModel):
    action_type: str
    category: Literal["reading", "activity", "entertainment", "social", "groups", "profile"]
    traffic_heavy: bool
    write_action: bool
    requires_premium: bool = False


class WarmupSelectableAccountRead(BaseModel):
    account_id: str
    display_name: str | None = None
    username: str | None = None
    phone_number: str
    role: str
    country: str
    country_iso: str
    validity_badge: Literal["valid", "needs_login", "blocked", "unknown"]
    proxy_badge: Literal["ok", "issue", "missing", "unknown"]
    phase_badge: Literal["new", "warming", "in_work"]
    tags: list[str] = Field(default_factory=list)
    is_in_work: bool = False


class WarmupExecutionModeRead(StrEnum):
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    PASSIVE = "passive"
    NETWORK = "network"
    ADVANCED = "advanced"


class WarmupPresetKindRead(StrEnum):
    EXPRESS = "express"
    STANDARD = "standard"
    HARDENED = "hardened"
    CUSTOM = "custom"


class WarmupSessionRead(BaseModel):
    id: str
    account_id: str
    strategy_id: str
    strategy_name: str
    status: WarmupStatusRead
    execution_mode: WarmupExecutionModeRead = WarmupExecutionModeRead.DRY_RUN
    duration_days: int = 14
    current_day: int
    cadence_hours: int
    timezone: str | None = None
    next_step_at: datetime | None = None
    last_step_at: datetime | None = None
    next_attempt_at: datetime | None = None
    next_micro_session_at: datetime | None = None
    last_micro_session_at: datetime | None = None
    cold_soak_until: datetime | None = None
    consecutive_failures: int
    daily_counters: dict[str, Any] = Field(default_factory=dict)
    trusted_peer_ids: list[str] = Field(default_factory=list)
    disabled_actions: list[str] = Field(default_factory=list)
    proxy_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None
    cycle_config: WarmupCycleConfigRead | None = None


class WarmupCyclicCreateRequest(BaseModel):
    account_ids: list[UuidString] = Field(min_length=1)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)
    days_total: int = Field(ge=1, le=30)
    strategy_preset: WarmupPresetKindRead = WarmupPresetKindRead.STANDARD


class WarmupCyclicCreateRead(BaseModel):
    items: list[WarmupSessionRead]


class WarmupSessionSummaryRead(BaseModel):
    id: str
    account_id: str
    account_label: str | None = None
    strategy_name: str
    status: WarmupStatusRead
    execution_mode: WarmupExecutionModeRead = WarmupExecutionModeRead.DRY_RUN
    duration_days: int = 14
    current_day: int
    cadence_hours: int
    next_step_at: datetime | None = None
    next_micro_session_at: datetime | None = None
    cold_soak_until: datetime | None = None
    updated_at: datetime
    cycle_config: WarmupCycleConfigRead | None = None


class WarmupSessionPageRead(BaseModel):
    items: list[WarmupSessionSummaryRead]
    total: int
    page: int
    limit: int


class WarmupSessionStatusRead(BaseModel):
    status: WarmupStatusRead
    current_day: int
    next_step_at: datetime | None = None
    next_attempt_at: datetime | None = None
    cold_soak_until: datetime | None = None


class WarmupPauseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class WarmupEventRead(BaseModel):
    id: str
    event_type: str
    severity: WarmupEventSeverityRead = WarmupEventSeverityRead.INFO
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WarmupEventPageRead(BaseModel):
    items: list[WarmupEventRead]
    total: int
    page: int
    limit: int


class WarmupLiveEventRead(BaseModel):
    id: str
    event_id: str
    session_id: str
    account_id: str
    account_label: str
    phone_id: str
    event_type: str
    severity: WarmupEventSeverityRead
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    created_at: datetime


class WarmupLiveEventAccountRead(BaseModel):
    account_id: str
    account_label: str
    phone_id: str


class WarmupLiveEventPageRead(BaseModel):
    items: list[WarmupLiveEventRead]
    total: int
    limit: int
    next_cursor: str | None = None
    accounts: list[WarmupLiveEventAccountRead] = Field(
        default_factory=list[WarmupLiveEventAccountRead]
    )


class WarmupStrategyRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_preset: bool
    preset_kind: WarmupPresetKindRead = WarmupPresetKindRead.CUSTOM
    execution_mode: WarmupExecutionModeRead = WarmupExecutionModeRead.DRY_RUN
    duration_days: int = 14
    daily_action_limits: dict[str, Any] = Field(default_factory=dict)
    session_window_config: dict[str, Any] = Field(default_factory=dict)
    ui_summary: dict[str, Any] = Field(default_factory=dict)


class WarmupIsolationClaimRead(BaseModel):
    account_id: str
    workspace_id: str
    held_by: str
    reason: str
    acquired_at: datetime


class WarmupIsolationStatusRead(BaseModel):
    is_isolated: bool
    claim: WarmupIsolationClaimRead | None = None


class WarmupReadinessRead(BaseModel):
    workers_enabled: bool
    dry_run: bool
    redis_connected: bool
    database_connected: bool
    active_sessions: int
    strategies_available: int


__all__ = [
    "WarmupBootstrapChannelCreate",
    "WarmupBootstrapChannelPatch",
    "WarmupBootstrapChannelRead",
    "WarmupCheckItemRead",
    "WarmupCheckSeverityRead",
    "WarmupCycleConfigRead",
    "WarmupCyclicCreateRead",
    "WarmupCyclicCreateRequest",
    "WarmupEventPageRead",
    "WarmupEventRead",
    "WarmupEventSeverityRead",
    "WarmupExecutionModeRead",
    "WarmupLiveEventAccountRead",
    "WarmupLiveEventPageRead",
    "WarmupLiveEventRead",
    "WarmupActionPresetRequest",
    "WarmupActionMetadataRead",
    "WarmupDisabledActionsRequest",
    "WarmupIsolationClaimRead",
    "WarmupIsolationStatusRead",
    "WarmupPauseRequest",
    "WarmupPresetKindRead",
    "WarmupProxyAdaptationRead",
    "WarmupReadinessRead",
    "WarmupSessionCreateRequest",
    "WarmupSessionPageRead",
    "WarmupSessionRead",
    "WarmupSessionStatusRead",
    "WarmupSessionSummaryRead",
    "WarmupStatusRead",
    "WarmupStrategyRead",
    "WarmupValidateRead",
    "WarmupValidateRequest",
]
