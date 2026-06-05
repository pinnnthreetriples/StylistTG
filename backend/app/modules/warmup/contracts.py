from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.types import UuidString


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


class WarmupValidateRequest(BaseModel):
    account_id: UuidString
    strategy_id: UuidString


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


class WarmupSessionCreateRequest(BaseModel):
    account_id: UuidString
    strategy_id: UuidString


class WarmupActionPresetRequest(BaseModel):
    preset: Literal["economic", "all", "minimal"]


class WarmupActionMetadataRead(BaseModel):
    action_type: str
    category: Literal["reading", "activity", "entertainment", "social", "groups", "profile"]
    traffic_heavy: bool
    write_action: bool
    requires_premium: bool = False


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
    proxy_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None


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
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WarmupEventPageRead(BaseModel):
    items: list[WarmupEventRead]
    total: int
    page: int
    limit: int


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
    "WarmupCheckItemRead",
    "WarmupCheckSeverityRead",
    "WarmupEventPageRead",
    "WarmupEventRead",
    "WarmupExecutionModeRead",
    "WarmupActionPresetRequest",
    "WarmupActionMetadataRead",
    "WarmupIsolationClaimRead",
    "WarmupIsolationStatusRead",
    "WarmupPauseRequest",
    "WarmupPresetKindRead",
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
