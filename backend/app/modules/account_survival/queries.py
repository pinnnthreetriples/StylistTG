from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy.orm import Session

from app.models import AccountSurvivalMetric
from app.modules.account_survival.contracts import (
    AccountSurvivalMetricRead,
    AccountSurvivalStrategyBreakdownRead,
    AccountSurvivalSummaryRead,
)
from app.modules.account_survival.repository import get_metric, list_metrics


def get_survival_summary(session: Session, *, workspace_id: str) -> AccountSurvivalSummaryRead:
    rows = list_metrics(session, workspace_id=workspace_id)
    days = sorted(row.survival_days for row in rows if row.survival_days is not None)
    return AccountSurvivalSummaryRead(
        total_accounts=len(rows),
        alive_count=sum(1 for row in rows if row.banned_at is None and row.deleted_at is None),
        banned_count=sum(1 for row in rows if row.banned_at is not None),
        deleted_count=sum(1 for row in rows if row.deleted_at is not None),
        mean_survival_days=float(mean(days)) if days else None,
        p50_survival_days=_percentile(days, 50),
        p90_survival_days=_percentile(days, 90),
        by_warmup_strategy=_strategy_breakdown(rows),
    )


def get_account_survival(
    session: Session, *, workspace_id: str, account_id: str
) -> AccountSurvivalMetricRead | None:
    row = get_metric(session, workspace_id=workspace_id, account_id=account_id)
    return _metric_read(row) if row is not None else None


def _metric_read(row: AccountSurvivalMetric) -> AccountSurvivalMetricRead:
    return AccountSurvivalMetricRead(
        account_id=row.account_id,
        imported_at=row.imported_at,
        warmup_started_at=row.warmup_started_at,
        warmup_completed_at=row.warmup_completed_at,
        pre_production_at=row.pre_production_at,
        first_action_after_warmup_at=row.first_action_after_warmup_at,
        first_freeze_at=row.first_freeze_at,
        first_unfreeze_at=row.first_unfreeze_at,
        freeze_count=row.freeze_count,
        flood_wait_count=row.flood_wait_count,
        banned_at=row.banned_at,
        deleted_at=row.deleted_at,
        survival_days=row.survival_days,
    )


def _percentile(values: list[int], percentile: int) -> int | None:
    if not values:
        return None
    index = round((len(values) - 1) * percentile / 100)
    return values[index]


def _strategy_breakdown(
    rows: list[AccountSurvivalMetric],
) -> list[AccountSurvivalStrategyBreakdownRead]:
    groups: dict[tuple[str | None, str | None], list[AccountSurvivalMetric]] = defaultdict(list)
    for row in rows:
        groups[(row.warmup_strategy_id, row.warmup_strategy_name)].append(row)
    return [
        AccountSurvivalStrategyBreakdownRead(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            total_accounts=len(items),
            alive_count=sum(
                1 for item in items if item.banned_at is None and item.deleted_at is None
            ),
            banned_count=sum(1 for item in items if item.banned_at is not None),
            deleted_count=sum(1 for item in items if item.deleted_at is not None),
        )
        for (strategy_id, strategy_name), items in groups.items()
    ]
