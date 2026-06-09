from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.contracts.queues import WARMUP_DISPATCH_QUEUE_NAME
from app.db import SessionLocal
from app.job_queue import workflows
from app.logging_utils import log_warn
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus
from app.modules.warmup.events import write_warmup_event


WARMUP_DUE_SESSIONS_JOB_ID = "warmup-due-sessions"
WARMUP_DISPATCH_TICK_JOB_ID = "warmup-dispatch-tick"
WARMUP_DISPATCH_SESSION_JOB_ID_PREFIX = "warmup-dispatch-session"
WARMUP_IDLE_SWEEP_JOB_ID = "warmup-idle-sweep"
WARMUP_BOOTSTRAP_CHANNEL_HEALTH_CHECK_JOB_ID = "warmup-bootstrap-channel-health-check"
_MAX_STAGGER_SPAN_SECONDS = 3600


def enqueue_warmup_due_sessions() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_due_sessions",
        job_id=WARMUP_DUE_SESSIONS_JOB_ID,
    )


def enqueue_warmup_dispatch_tick() -> bool:
    if _stagger_enabled():
        with SessionLocal() as session:
            return enqueue_due_warmup_dispatch_sessions(session)
    return workflows.enqueue_workflow(
        workflow_type="warmup_dispatch_tick",
        job_id=WARMUP_DISPATCH_TICK_JOB_ID,
    )


def enqueue_warmup_idle_sweep() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_idle_sweep",
        job_id=WARMUP_IDLE_SWEEP_JOB_ID,
    )


def enqueue_warmup_bootstrap_channel_health_check() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_bootstrap_channel_health_check",
        job_id=WARMUP_BOOTSTRAP_CHANNEL_HEALTH_CHECK_JOB_ID,
    )


def enqueue_due_warmup_dispatch_sessions(
    session: Session,
    *,
    now: datetime | None = None,
    queue: Any | None = None,
    rng: random.Random | None = None,
    limit: int | None = None,
) -> bool:
    timestamp = _aware_utc(now or datetime.now(UTC))
    queue = queue or _dispatch_queue()
    rng = rng or random.Random()
    from app.modules.warmup.jobs import run_warmup_dispatch_session

    cursors: dict[str, datetime] = {}
    scheduled_count = 0
    for warmup_session in _due_dispatch_sessions(session, now=timestamp, limit=limit):
        workspace_id = warmup_session.workspace_id
        cursor = cursors.get(workspace_id, timestamp)
        cursor = cursor + timedelta(seconds=_next_stagger_delay(rng))
        if (cursor - timestamp).total_seconds() > _MAX_STAGGER_SPAN_SECONDS:
            break
        job_id = f"{WARMUP_DISPATCH_SESSION_JOB_ID_PREFIX}-{warmup_session.id}"
        try:
            cast(Any, queue).enqueue_at(
                cursor,
                run_warmup_dispatch_session,
                warmup_session.id,
                cursor.isoformat(),
                job_id=job_id,
            )
        except RedisError:
            log_warn(
                "warmup_dispatch_stagger_enqueue_failed",
                queue_name=WARMUP_DISPATCH_QUEUE_NAME,
                warmup_session_id=warmup_session.id,
                error_class="RedisError",
            )
            session.rollback()
            return False
        warmup_session.next_micro_session_at = cursor
        warmup_session.next_step_at = cursor
        write_warmup_event(
            session,
            warmup_session,
            "connection_stagger_scheduled",
            {
                "scheduled_at": cursor.isoformat(),
                "job_id": job_id,
                "stagger_min_seconds": settings.warmup_connection_stagger_min_seconds,
                "stagger_max_seconds": settings.warmup_connection_stagger_max_seconds,
            },
        )
        cursors[workspace_id] = cursor
        scheduled_count += 1
    if scheduled_count:
        session.commit()
    return True


def _due_dispatch_sessions(
    session: Session,
    *,
    now: datetime,
    limit: int | None,
) -> list[WarmupSession]:
    # System-wide dispatcher: scans warmup sessions across workspaces by design
    # (worker enqueues dispatch jobs for every tenant). Tenant isolation happens
    # downstream in the dispatch job itself.
    query = select(WarmupSession).where(  # nosemgrep: semgrep.missing-workspace-id-filter
        WarmupSession.execution_mode != WarmupExecutionMode.DRY_RUN.value,
        (
            (
                WarmupSession.status.in_([WarmupStatus.SCHEDULED.value, WarmupStatus.ACTIVE.value])
                & (
                    WarmupSession.next_micro_session_at.is_(None)
                    | (WarmupSession.next_micro_session_at <= now)
                )
            )
            | (
                (WarmupSession.status == WarmupStatus.COLD_SOAK.value)
                & (
                    WarmupSession.next_micro_session_at.is_(None)
                    | (WarmupSession.next_micro_session_at <= now)
                    | (WarmupSession.cold_soak_until <= now)
                )
            )
        ),
    )
    query = query.order_by(
        WarmupSession.workspace_id.asc(),
        WarmupSession.next_micro_session_at.asc(),
        WarmupSession.updated_at.asc(),
    ).limit(limit or settings.warmup_batch_limit)
    return list(session.execute(query).scalars().all())


def _next_stagger_delay(rng: random.Random) -> int:
    min_seconds = max(0, int(settings.warmup_connection_stagger_min_seconds))
    max_seconds = max(min_seconds, int(settings.warmup_connection_stagger_max_seconds))
    if max_seconds <= 0:
        return 0
    return rng.randint(min_seconds, max_seconds)


def _stagger_enabled() -> bool:
    return (
        max(
            int(settings.warmup_connection_stagger_min_seconds),
            int(settings.warmup_connection_stagger_max_seconds),
        )
        > 0
    )


def _dispatch_queue() -> Any:
    from app.job_queue.rq import get_queue

    return get_queue(WARMUP_DISPATCH_QUEUE_NAME)


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


__all__ = [
    "WARMUP_BOOTSTRAP_CHANNEL_HEALTH_CHECK_JOB_ID",
    "WARMUP_DISPATCH_SESSION_JOB_ID_PREFIX",
    "WARMUP_DISPATCH_TICK_JOB_ID",
    "WARMUP_DUE_SESSIONS_JOB_ID",
    "WARMUP_IDLE_SWEEP_JOB_ID",
    "enqueue_due_warmup_dispatch_sessions",
    "enqueue_warmup_bootstrap_channel_health_check",
    "enqueue_warmup_dispatch_tick",
    "enqueue_warmup_due_sessions",
    "enqueue_warmup_idle_sweep",
]
