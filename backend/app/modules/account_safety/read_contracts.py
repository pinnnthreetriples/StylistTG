from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def _empty_operation_cooldowns() -> list[AccountOperationCooldownRead]:
    return []


class AccountSafetyReasonRead(BaseModel):
    code: str
    severity: str
    source: str
    message: str
    last_seen_at: datetime | None = None


class AccountCapabilityRead(BaseModel):
    state: str
    reason_codes: list[str]
    label: str
    last_checked_at: datetime | None = None
    source: str


class AccountRiskRead(BaseModel):
    level: str
    reasons: list[AccountSafetyReasonRead]


class AccountOperationCooldownRead(BaseModel):
    id: str
    account_id: str
    operation: str
    level: str
    reason_code: str
    started_at: datetime
    retry_after_at: datetime
    source: str
    source_job_id: str | None = None
    source_step_id: str | None = None


class AccountSafetySummaryRead(BaseModel):
    account_id: str
    health_status: str
    overall_risk_level: str
    validity_status: str
    proxy_status: str = "none"
    capability_summary: dict[str, str]
    cooldown_summary: list[AccountOperationCooldownRead] = Field(
        default_factory=_empty_operation_cooldowns
    )
    top_reasons: list[AccountSafetyReasonRead]
    last_checked_at: datetime
    source: str


class AccountOperationSafetyRead(BaseModel):
    operation: str
    state: str
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    cooldowns: list[AccountOperationCooldownRead] = Field(
        default_factory=_empty_operation_cooldowns
    )
    can_override: bool = False


class AccountValidityCheckRead(BaseModel):
    id: str
    account_id: str
    mode: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_class: str | None
    details: dict[str, Any] | None
    result: dict[str, Any] | None
    created_at: datetime


class AccountSafetyRead(AccountSafetySummaryRead):
    capabilities: dict[str, AccountCapabilityRead]
    risk_by_operation: dict[str, AccountRiskRead]
    cooldowns_by_operation: dict[str, list[AccountOperationCooldownRead]]
    reasons: list[AccountSafetyReasonRead]
    last_validity_check: AccountValidityCheckRead | None = None


__all__ = [
    "AccountCapabilityRead",
    "AccountOperationCooldownRead",
    "AccountOperationSafetyRead",
    "AccountRiskRead",
    "AccountSafetyRead",
    "AccountSafetyReasonRead",
    "AccountSafetySummaryRead",
    "AccountValidityCheckRead",
]
