from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import time
from typing import Any, cast

from redis.exceptions import RedisError

from app.config import Settings, settings
from app.db import SessionLocal
from app.logging_utils import log_warn
from app.models import utc_now
from app.modules.account_safety.status_monitor import run_account_status_monitor_tick
from app.modules.account_survival.metrics_updater import update_survival_metrics_workflow
from app.services.admin_notifications import collect_triggers, deliver, is_recently_notified
from app.services.notification_channels import EmailNotifier, WebhookNotifier
from app.services.worker_plane import MAINTENANCE_QUEUE_NAME, SCHEDULER_QUEUE_NAME

ACCOUNT_STATUS_MONITOR_TICK_SECONDS = 600
NOTIFICATION_COLLECTION_TICK_SECONDS = 300
ADMIN_NOTIFICATION_JOB_ID_PREFIX = "admin-notification"
RETENTION_TICK_SECONDS = 86_400
RATE_LIMIT_FLUSH_TICK_SECONDS = 60
RATE_LIMIT_FLUSH_JOB_ID_PREFIX = "rate-limit-flush"
RECONCILE_STUCK_TICK_SECONDS = 120
RECONCILE_STUCK_JOB_ID_PREFIX = "reconcile-stuck-attempts"
SURVIVAL_METRICS_TICK_SECONDS = 3_600
SURVIVAL_METRICS_JOB_ID_PREFIX = "account-survival-metrics"


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
            "admin_notifications": NOTIFICATION_COLLECTION_TICK_SECONDS,
            "retention": RETENTION_TICK_SECONDS,
            "rate_limit_flush": RATE_LIMIT_FLUSH_TICK_SECONDS,
            "reconcile_stuck_attempts": RECONCILE_STUCK_TICK_SECONDS,
            "account_survival_metrics": SURVIVAL_METRICS_TICK_SECONDS,
        },
    )


def account_status_monitor_tick() -> int:
    with SessionLocal() as session:
        report = run_account_status_monitor_tick(session)
        session.commit()
        return report.processed_count


def admin_notification_tick() -> dict[str, int]:
    with SessionLocal() as session:
        payloads = collect_triggers(session, now=utc_now())
        delivered = 0
        skipped = 0
        channels = [EmailNotifier(), WebhookNotifier()]
        for payload in payloads:
            if is_recently_notified(
                session,
                workspace_id=str(payload.workspace_id),
                trigger_code=payload.trigger_code,
            ):
                skipped += 1
                continue
            deliver(session, payload, channels=channels)
            delivered += 1
        session.commit()
        return {"delivered": delivered, "skipped": skipped, "candidates": len(payloads)}


def enqueue_admin_notification_tick(*, now: float | None = None) -> bool:
    """Enqueue one admin notification job for the current five-minute bucket."""
    from app.job_queue.rq import get_queue

    bucket = int((time.time() if now is None else now) // NOTIFICATION_COLLECTION_TICK_SECONDS)
    job_id = f"{ADMIN_NOTIFICATION_JOB_ID_PREFIX}-{bucket}"
    queue = get_queue(SCHEDULER_QUEUE_NAME)
    try:
        cast(Any, queue).enqueue_call(
            func=admin_notification_tick,
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        log_warn(
            "admin_notification_enqueue_failed",
            queue_name=SCHEDULER_QUEUE_NAME,
            job_id=job_id,
            error_class="RedisError",
        )
        return False
    return True


def rate_limit_flush_tick() -> dict[str, object]:
    """Flush rate-limit counters from Redis to Postgres (persistence fallback)."""
    from app.services.rate_limit_persistence import flush_redis_to_db
    from app.services.redis_client import redis_from_url

    redis_client = redis_from_url()
    with SessionLocal() as session:
        report = flush_redis_to_db(session, redis_client)
        session.commit()
    return {"scopes": report.per_scope_counts, "upserted": report.upserted}


def reconcile_stuck_tick() -> dict[str, object]:
    """Reconcile stuck NeuroCommenting attempts via TDLib message lookup."""
    from app.services.reconcile_stuck_attempts import RuntimeTdlibSearchClient, run_reconcile_tick

    with SessionLocal() as session:
        report = run_reconcile_tick(session, RuntimeTdlibSearchClient(), now=utc_now())
        session.commit()
    return cast(dict[str, object], asdict(report))


def enqueue_rate_limit_flush_tick(*, now: float | None = None) -> bool:
    """Enqueue one rate-limit flush job for the current scheduler minute bucket."""
    from app.job_queue.rq import get_queue

    bucket = int((time.time() if now is None else now) // RATE_LIMIT_FLUSH_TICK_SECONDS)
    job_id = f"{RATE_LIMIT_FLUSH_JOB_ID_PREFIX}-{bucket}"
    queue = get_queue(SCHEDULER_QUEUE_NAME)
    try:
        cast(Any, queue).enqueue_call(
            func=rate_limit_flush_tick,
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        log_warn(
            "rate_limit_flush_enqueue_failed",
            queue_name=SCHEDULER_QUEUE_NAME,
            job_id=job_id,
            error_class="RedisError",
        )
        return False
    return True


def enqueue_reconcile_stuck_tick(*, now: float | None = None) -> bool:
    """Enqueue one stuck-attempt reconcile job for the current two-minute bucket."""
    from app.job_queue.rq import get_queue

    bucket = int((time.time() if now is None else now) // RECONCILE_STUCK_TICK_SECONDS)
    job_id = f"{RECONCILE_STUCK_JOB_ID_PREFIX}-{bucket}"
    queue = get_queue(SCHEDULER_QUEUE_NAME)
    try:
        cast(Any, queue).enqueue_call(
            func=reconcile_stuck_tick,
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        log_warn(
            "reconcile_stuck_enqueue_failed",
            queue_name=SCHEDULER_QUEUE_NAME,
            job_id=job_id,
            error_class="RedisError",
        )
        return False
    return True


def enqueue_survival_metrics_tick(*, now: float | None = None) -> bool:
    """Enqueue one survival metrics refresh job for the current hourly bucket."""
    from app.job_queue.rq import get_queue

    bucket = int((time.time() if now is None else now) // SURVIVAL_METRICS_TICK_SECONDS)
    job_id = f"{SURVIVAL_METRICS_JOB_ID_PREFIX}-{bucket}"
    queue = get_queue(MAINTENANCE_QUEUE_NAME)
    try:
        cast(Any, queue).enqueue_call(
            func=update_survival_metrics_workflow,
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        log_warn(
            "survival_metrics_enqueue_failed",
            queue_name=MAINTENANCE_QUEUE_NAME,
            job_id=job_id,
            error_class="RedisError",
        )
        return False
    return True


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
