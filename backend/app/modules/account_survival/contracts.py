from __future__ import annotations

# pyright: reportUnknownVariableType=false

from datetime import datetime

from pydantic import BaseModel, Field


class AccountSurvivalStrategyBreakdownRead(BaseModel):
    strategy_id: str | None = None
    strategy_name: str | None = None
    total_accounts: int
    alive_count: int
    banned_count: int
    deleted_count: int


def _empty_strategy_breakdown() -> list[AccountSurvivalStrategyBreakdownRead]:
    return []


class AccountSurvivalSummaryRead(BaseModel):
    total_accounts: int
    alive_count: int
    banned_count: int
    deleted_count: int
    mean_survival_days: float | None = None
    p50_survival_days: int | None = None
    p90_survival_days: int | None = None
    by_warmup_strategy: list[AccountSurvivalStrategyBreakdownRead] = Field(
        default_factory=_empty_strategy_breakdown
    )


class AccountSurvivalMetricRead(BaseModel):
    account_id: str
    imported_at: datetime
    warmup_started_at: datetime | None = None
    warmup_completed_at: datetime | None = None
    pre_production_at: datetime | None = None
    first_action_after_warmup_at: datetime | None = None
    first_freeze_at: datetime | None = None
    first_unfreeze_at: datetime | None = None
    freeze_count: int
    flood_wait_count: int
    banned_at: datetime | None = None
    deleted_at: datetime | None = None
    survival_days: int | None = None
