from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AccountSurvivalMetric, WarmupChannelState
from app.modules.account_survival.metrics import AccountSurvivalMetrics, account_survival_metrics
from app.modules.account_survival.queries import get_survival_summary
from app.modules.warmup.channel_state.health import (
    HEALTH_THRESHOLD_EXCLUDE,
    HEALTH_THRESHOLD_WARN,
)

SURVIVAL_METRICS_WORKFLOW_TYPE = "account_survival.metrics.update"


def update_survival_metrics(
    session: Session,
    *,
    metrics: AccountSurvivalMetrics = account_survival_metrics,
) -> int:
    processed = 0
    for workspace_id in _workspace_ids(session):
        summary = get_survival_summary(session, workspace_id=workspace_id)
        metrics.account_survival_current(
            state="alive", workspace_id=workspace_id, value=summary.alive_count
        )
        metrics.account_survival_current(
            state="banned", workspace_id=workspace_id, value=summary.banned_count
        )
        metrics.account_survival_current(
            state="deleted", workspace_id=workspace_id, value=summary.deleted_count
        )
        metrics.account_survival_days(
            percentile="mean",
            workspace_id=workspace_id,
            value=summary.mean_survival_days,
        )
        metrics.account_survival_days(
            percentile="p50",
            workspace_id=workspace_id,
            value=summary.p50_survival_days,
        )
        metrics.account_survival_days(
            percentile="p90",
            workspace_id=workspace_id,
            value=summary.p90_survival_days,
        )
        _update_channel_health(session, workspace_id=workspace_id, metrics=metrics)
        processed += 1
    return processed


def update_survival_metrics_workflow() -> int:
    with SessionLocal() as session:
        return update_survival_metrics(session)


def _workspace_ids(session: Session) -> list[str]:
    survival_ids = session.execute(select(AccountSurvivalMetric.workspace_id).distinct()).scalars()
    channel_ids = session.execute(select(WarmupChannelState.workspace_id).distinct()).scalars()
    return sorted({workspace_id for workspace_id in [*survival_ids, *channel_ids] if workspace_id})


def _update_channel_health(
    session: Session,
    *,
    workspace_id: str,
    metrics: AccountSurvivalMetrics,
) -> None:
    rows = session.execute(
        select(WarmupChannelState.health_score).where(
            WarmupChannelState.workspace_id == workspace_id
        )
    ).scalars()
    counts: Counter[str] = Counter(_health_bucket(score) for score in rows)
    for bucket in ("healthy", "warning", "blacklisted"):
        metrics.channel_health(bucket=bucket, workspace_id=workspace_id, value=counts[bucket])


def _health_bucket(score: float) -> str:
    if score < HEALTH_THRESHOLD_EXCLUDE:
        return "blacklisted"
    if score < HEALTH_THRESHOLD_WARN:
        return "warning"
    return "healthy"


__all__ = [
    "SURVIVAL_METRICS_WORKFLOW_TYPE",
    "update_survival_metrics",
    "update_survival_metrics_workflow",
]
