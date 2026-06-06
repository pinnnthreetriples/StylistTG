"""Warmup dispatch service facade."""

from __future__ import annotations

# pyright: reportPrivateUsage=false

import logging
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import WarmupTextProvider, build_warmup_text_provider
from app.adapters.warmup_tdlib import WarmupTdlibAdapter, build_warmup_tdlib_adapter
from app.config import settings
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

logger = logging.getLogger(__name__)

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
    "process_due_warmup_dispatches",
]


def _isolation_owner(session_id: str) -> str:
    return f"warmup:{session_id}"


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
