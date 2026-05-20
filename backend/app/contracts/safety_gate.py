from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator


WorkspaceSafetyMode = Literal["conservative", "balanced", "aggressive"]
MinuteOfDay = Annotated[int, Field(ge=0, le=1439)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
SafetyGateIntent = Literal["editing", "warmup", "commenting"]
SafetyGateReasonCode = Literal[
    "proxy_unhealthy",
    "no_warmup",
    "warmup_incomplete",
    "age_too_low",
    "flood_wait_streak",
    "fraud_score_high",
    "ggr_too_low",
    "status_degraded",
    "profile_incomplete",
    "active_quarantine",
    "cross_module_overload",
    "terminal_status",
    "ip_change_cooldown",
]
SafetyGateReasonSeverity = Literal["warning", "blocked"]
SafetyGateVerdictSeverity = Literal["ok", "warning", "blocked"]


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class WorkspaceSafetyPolicyRead(BaseModel):
    id: str
    workspace_id: str
    mode: WorkspaceSafetyMode
    delay_multiplier: Annotated[float, Field(gt=0.0)]
    typing_chars_per_minute_min: NonNegativeInt | None
    typing_chars_per_minute_max: NonNegativeInt | None
    profile_view_probability: Probability
    scroll_probability: Probability
    typo_probability: Probability
    message_deletion_probability: Probability
    quiet_hours_local_start: MinuteOfDay | None
    quiet_hours_local_end: MinuteOfDay | None
    require_warmup_before_commenting: bool
    min_warmup_days: NonNegativeInt
    require_healthy_proxy: bool
    min_account_age_hours: NonNegativeInt
    auto_pause_on_flood_wait_count: NonNegativeInt
    auto_pause_on_deleted_comments_count: NonNegativeInt
    quarantine_hours_on_flood_wait: NonNegativeInt
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class WorkspaceSafetyPolicyUpdate(BaseModel):
    mode: WorkspaceSafetyMode | None = None
    delay_multiplier: Annotated[float, Field(gt=0.0)] | None = None
    typing_chars_per_minute_min: NonNegativeInt | None = None
    typing_chars_per_minute_max: NonNegativeInt | None = None
    profile_view_probability: Probability | None = None
    scroll_probability: Probability | None = None
    typo_probability: Probability | None = None
    message_deletion_probability: Probability | None = None
    quiet_hours_local_start: MinuteOfDay | None = None
    quiet_hours_local_end: MinuteOfDay | None = None
    require_warmup_before_commenting: StrictBool | None = None
    min_warmup_days: NonNegativeInt | None = None
    require_healthy_proxy: StrictBool | None = None
    min_account_age_hours: NonNegativeInt | None = None
    auto_pause_on_flood_wait_count: NonNegativeInt | None = None
    auto_pause_on_deleted_comments_count: NonNegativeInt | None = None
    quarantine_hours_on_flood_wait: NonNegativeInt | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "typing_chars_per_minute_min",
        "typing_chars_per_minute_max",
        "quiet_hours_local_start",
        "quiet_hours_local_end",
        "min_warmup_days",
        "min_account_age_hours",
        "auto_pause_on_flood_wait_count",
        "auto_pause_on_deleted_comments_count",
        "quarantine_hours_on_flood_wait",
        mode="before",
    )
    @classmethod
    def _reject_bool_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        return value


class SafetyGateReason(BaseModel):
    code: SafetyGateReasonCode
    severity: SafetyGateReasonSeverity
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SafetyGateVerdict(BaseModel):
    account_id: UUID
    intent: SafetyGateIntent
    eligible: bool
    severity: SafetyGateVerdictSeverity
    reasons: list[SafetyGateReason]
    ggr_score: float | None
    checked_at: datetime
    cache_ttl_seconds: int

    @field_serializer("checked_at")
    def _serialize_checked_at(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


__all__ = [
    "WorkspaceSafetyMode",
    "WorkspaceSafetyPolicyRead",
    "WorkspaceSafetyPolicyUpdate",
    "SafetyGateIntent",
    "SafetyGateReason",
    "SafetyGateReasonCode",
    "SafetyGateVerdict",
]
