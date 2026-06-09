"""Warmup dispatch service facade."""

from __future__ import annotations

# pyright: reportPrivateUsage=false

import logging
import random
from datetime import datetime
from datetime import UTC, timedelta
from typing import Any, cast

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import WarmupTextProvider, build_warmup_text_provider
from app.adapters.warmup_tdlib import WarmupTdlibAdapter, build_warmup_tdlib_adapter
from app.config import settings
from app.contracts.queues import WARMUP_DISPATCH_QUEUE_NAME
from app.logging_utils import log_warn
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus, utc_now
from app.modules.account_safety.interfaces import evaluate as evaluate_safety_gate

from .dispatch_actions import _execute_live_action
from .dispatch_context import (
    _ActionContextResolution,
    _derive_text_seed,
    _resolve_action_context,
    _select_chat_target,
)
from .dispatch_processor import _process_one_dispatch
from .dispatch_results import _complete_dispatch_session
from .dispatch_schedule import (
    DEFAULT_ACTION_PRIORITY,
    MAX_ACTIONS_PER_MICRO_SESSION,
    _is_day_complete,
    _is_hour_in_quiet_window,
    _is_in_quiet_hours,
    _local_hour,
    _max_retry_after_seconds,
    _next_day_first_window,
    _next_quiet_hours_end,
    _persist_day_counters,
    _resolve_day_counters,
    _resolve_day_plan,
    _resolve_timezone,
    _schedule_within_day,
    _select_action_targets,
    _select_actions_for_window,
)
from .enqueue import WARMUP_DISPATCH_SESSION_JOB_ID_PREFIX
from .events import write_warmup_event

logger = logging.getLogger(__name__)
_MAX_STAGGER_SPAN_SECONDS = 3600

__all__ = [
    "DEFAULT_ACTION_PRIORITY",
    "MAX_ACTIONS_PER_MICRO_SESSION",
    "_ActionContextResolution",
    "_complete_dispatch_session",
    "_derive_text_seed",
    "_execute_live_action",
    "evaluate_safety_gate",
    "_is_day_complete",
    "_is_hour_in_quiet_window",
    "_is_in_quiet_hours",
    "_isolation_owner",
    "_local_hour",
    "_max_retry_after_seconds",
    "_next_day_first_window",
    "_next_quiet_hours_end",
    "_persist_day_counters",
    "_process_one_dispatch",
    "_resolve_action_context",
    "_resolve_day_counters",
    "_resolve_day_plan",
    "_resolve_timezone",
    "_schedule_within_day",
    "_select_action_targets",
    "_select_actions_for_window",
    "_select_chat_target",
    "enqueue_due_warmup_dispatch_sessions",
    "process_due_warmup_dispatches",
    "process_warmup_dispatch_session",
]


def _isolation_owner(session_id: str) -> str:
    return f"warmup:{session_id}"


def enqueue_due_warmup_dispatch_sessions(
    session: Session,
    *,
    now: datetime | None = None,
    workspace_id: str | None = None,
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
    for warmup_session in _due_dispatch_sessions(
        session,
        now=timestamp,
        workspace_id=workspace_id,
        limit=limit,
    ):
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


def process_due_warmup_dispatches(
    session: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    workspace_id: str | None = None,
    limit: int | None = None,
    rng: random.Random | None = None,
    passive_adapter: WarmupTdlibAdapter | None = None,
    text_provider: WarmupTextProvider | None = None,
) -> int:
    """Pick up sessions whose micro-session window is due and tick them.

    Returns the count of sessions that produced at least one state change.
    Live execution_mode'ы (`passive`/`network`/`advanced`) делегируют
    действия в `passive_adapter`; `shadow` остаётся в чистой симуляции.
    Адаптер закрывается в `finally`, чтобы TDLib-клиенты не текли между
    тиками.
    """
    timestamp = now or utc_now()
    rng = rng or random.Random()
    adapter = passive_adapter if passive_adapter is not None else build_warmup_tdlib_adapter()
    provider = text_provider if text_provider is not None else build_warmup_text_provider()
    workspace_scope = workspace_id if workspace_id is not None else WarmupSession.workspace_id

    query = select(WarmupSession).where(
        WarmupSession.workspace_id == workspace_scope,
        WarmupSession.execution_mode != WarmupExecutionMode.DRY_RUN.value,
        (
            (
                WarmupSession.status.in_([WarmupStatus.SCHEDULED.value, WarmupStatus.ACTIVE.value])
                & (
                    WarmupSession.next_micro_session_at.is_(None)
                    | (WarmupSession.next_micro_session_at <= timestamp)
                )
            )
            | (
                (WarmupSession.status == WarmupStatus.COLD_SOAK.value)
                & (
                    WarmupSession.next_micro_session_at.is_(None)
                    | (WarmupSession.next_micro_session_at <= timestamp)
                    | (WarmupSession.cold_soak_until <= timestamp)
                )
            )
        ),
    )
    include_live_modes = bool(settings.warmup_live_enabled or passive_adapter is not None)
    if not include_live_modes:
        query = query.where(WarmupSession.execution_mode == WarmupExecutionMode.SHADOW.value)
    query = query.order_by(WarmupSession.updated_at.asc()).limit(
        limit or settings.warmup_batch_limit
    )

    processed = 0
    try:
        for warmup_session in session.execute(query).scalars().all():
            if _process_one_dispatch(
                session,
                warmup_session,
                now=timestamp,
                worker_id=worker_id,
                rng=rng,
                adapter=adapter,
                text_provider=provider,
            ):
                processed += 1
        session.commit()
    finally:
        try:
            adapter.close()
        except Exception as exc:
            logger.debug("Warmup adapter cleanup failed: %s", exc, exc_info=True)
    return processed


def _due_dispatch_sessions(
    session: Session,
    *,
    now: datetime,
    workspace_id: str | None,
    limit: int | None,
) -> list[WarmupSession]:
    workspace_scope = workspace_id if workspace_id is not None else WarmupSession.workspace_id
    query = select(WarmupSession).where(
        WarmupSession.workspace_id == workspace_scope,
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


def dispatch_stagger_enabled() -> bool:
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


def process_warmup_dispatch_session(
    session: Session,
    *,
    session_id: str,
    worker_id: str,
    now: datetime | None = None,
    rng: random.Random | None = None,
    passive_adapter: WarmupTdlibAdapter | None = None,
    text_provider: WarmupTextProvider | None = None,
) -> int:
    timestamp = now or utc_now()
    warmup_session = session.get(WarmupSession, session_id)
    if warmup_session is None or warmup_session.execution_mode == WarmupExecutionMode.DRY_RUN.value:
        return 0
    include_live_modes = bool(settings.warmup_live_enabled or passive_adapter is not None)
    if not include_live_modes and warmup_session.execution_mode != WarmupExecutionMode.SHADOW.value:
        return 0
    if not _dispatch_session_due(warmup_session, timestamp):
        return 0

    rng = rng or random.Random()
    adapter = passive_adapter if passive_adapter is not None else build_warmup_tdlib_adapter()
    provider = text_provider if text_provider is not None else build_warmup_text_provider()
    try:
        processed = int(
            _process_one_dispatch(
                session,
                warmup_session,
                now=timestamp,
                worker_id=worker_id,
                rng=rng,
                adapter=adapter,
                text_provider=provider,
            )
        )
        session.commit()
        return processed
    finally:
        try:
            adapter.close()
        except Exception as exc:
            logger.debug("Warmup adapter cleanup failed: %s", exc, exc_info=True)


def _dispatch_session_due(warmup_session: WarmupSession, now: datetime) -> bool:
    if warmup_session.status in {WarmupStatus.SCHEDULED.value, WarmupStatus.ACTIVE.value}:
        return _is_due_at(warmup_session.next_micro_session_at, now)
    if warmup_session.status == WarmupStatus.COLD_SOAK.value:
        return _is_due_at(warmup_session.next_micro_session_at, now) or (
            warmup_session.cold_soak_until is not None
            and _is_due_at(warmup_session.cold_soak_until, now)
        )
    return False


def _is_due_at(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return True
    if value.tzinfo is None and now.tzinfo is not None:
        value = value.replace(tzinfo=now.tzinfo)
    if value.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=value.tzinfo)
    return value <= now
