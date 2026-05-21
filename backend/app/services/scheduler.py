from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from redis.exceptions import RedisError

from app.config import Settings, settings
from app.db import SessionLocal
from app.logging_utils import log_warn
from app.services.account_status_monitor import run_account_status_monitor_tick
from app.services.worker_plane import SCHEDULER_QUEUE_NAME

ACCOUNT_STATUS_MONITOR_TICK_SECONDS = 600
RETENTION_TICK_SECONDS = 86_400


@dataclass(frozen=True)
class SchedulerReport:
    enabled: bool
    mode: str
    planned_queues: list[str]
    planned_ticks: dict[str, int]
    destructive_actions_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "planned_queues": self.planned_queues,
            "planned_ticks": self.planned_ticks,
            "destructive_actions_enabled": self.destructive_actions_enabled,
        }


def scheduler_report(config: Settings = settings) -> SchedulerReport:
    return SchedulerReport(
        enabled=config.scheduler_enabled,
        mode="report_only" if not config.scheduler_enabled else "safe_enqueue",
        planned_queues=["scheduler_jobs", "maintenance_jobs"],
        planned_ticks={
            "account_status_monitor": ACCOUNT_STATUS_MONITOR_TICK_SECONDS,
            "retention": RETENTION_TICK_SECONDS,
        },
    )


def account_status_monitor_tick() -> int:
    with SessionLocal() as session:
        observations = run_account_status_monitor_tick(session)
        session.commit()
        return len(observations)


def schedule_bought_onboarding_action(
    action: str,
    *,
    account_id: str,
    workspace_id: str,
    run_at: datetime,
) -> bool:
    from app.job_queue.rq import get_queue
    from app.services.bought_account_onboarding import (
        run_rest_period_ggr_check,
        run_terminate_other_sessions,
    )

    handlers = {
        "terminate_other_sessions": run_terminate_other_sessions,
        "ggr_precheck": run_rest_period_ggr_check,
    }
    handler = handlers.get(action)
    if handler is None:
        raise ValueError(f"unsupported bought onboarding action: {action}")

    queue = get_queue(SCHEDULER_QUEUE_NAME)
    job_id = f"bought-onboarding-{action}-{workspace_id}-{account_id}"
    try:
        cast(Any, queue).enqueue_at(run_at, handler, account_id, workspace_id, job_id=job_id)
    except RedisError:
        log_warn(
            "bought_onboarding_schedule_failed",
            action=action,
            queue_name=SCHEDULER_QUEUE_NAME,
            account_id=account_id,
            error_class="RedisError",
        )
        return False
    return True
