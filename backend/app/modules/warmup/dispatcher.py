"""Warmup dispatch service (Phase 1..4).

DRY_RUN сессии по-прежнему ведёт `warmup_worker.process_due_warmup_sessions`
по плоской каденции. Для всех остальных режимов (`shadow`, `passive`,
`network`, `advanced`) день не двигается просто по таймеру: внутри дня
открывается несколько микро-сессий, каждая из которых выполняет небольшую
порцию действий из `daily_action_limits`.

Поведение по execution_mode:
- shadow:   pure simulation (никаких TDLib-вызовов).
- passive:  read-only TDLib через `WarmupTdlibAdapter`.
- network:  passive + safe-write `join_chat` (источник — strategy.target_channels_json).
- advanced: network + write `p2p_send` к eligible-peer'у (текст —
  `WarmupTextProvider.compose_p2p_message`).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import (
    TextVariationRequest,
    WarmupTextProvider,
    build_warmup_text_provider,
)
from app.adapters.warmup_tdlib import (
    WRITE_ACTION_TYPES,
    WarmupActionResult,
    WarmupTdlibAdapter,
    build_warmup_tdlib_adapter,
)
from app.config import settings
from app.models import (
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    utc_now,
)
from app.services.account_safety_gate import evaluate as evaluate_safety_gate
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import release_claim
from app.modules.warmup.worker import handle_warmup_step_failure
from app.modules.warmup.p2p import (
    record_p2p_contact,
    select_eligible_peer,
)

DEFAULT_ACTION_PRIORITY = ("feed_read", "join_chat", "p2p_send")
MAX_ACTIONS_PER_MICRO_SESSION = 3


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

    query = select(WarmupSession).where(
        WarmupSession.status.in_([WarmupStatus.SCHEDULED.value, WarmupStatus.ACTIVE.value]),
        WarmupSession.execution_mode != WarmupExecutionMode.DRY_RUN.value,
        (WarmupSession.next_micro_session_at.is_(None))
        | (WarmupSession.next_micro_session_at <= timestamp),
    )
    include_live_modes = bool(settings.warmup_live_enabled or passive_adapter is not None)
    if not include_live_modes:
        query = query.where(WarmupSession.execution_mode == WarmupExecutionMode.SHADOW.value)
    if workspace_id is not None:
        query = query.where(WarmupSession.workspace_id == workspace_id)
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
        except Exception:  # adapter cleanup must never break the worker
            pass
    return processed


_LIVE_EXECUTION_MODES: frozenset[str] = frozenset(
    {
        WarmupExecutionMode.PASSIVE.value,
        WarmupExecutionMode.NETWORK.value,
        WarmupExecutionMode.ADVANCED.value,
    }
)


def _process_one_dispatch(
    session: Session,
    warmup_session: WarmupSession,
    *,
    now: datetime,
    worker_id: str,
    rng: random.Random,
    adapter: WarmupTdlibAdapter,
    text_provider: WarmupTextProvider,
) -> bool:
    if _is_in_quiet_hours(now, warmup_session.timezone):
        quiet_hours_end = _next_quiet_hours_end(now, warmup_session.timezone)
        warmup_session.next_micro_session_at = quiet_hours_end
        warmup_session.updated_at = now
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {
                "reason": "quiet_hours",
                "reschedule_at": quiet_hours_end.isoformat(),
            },
        )
        session.flush()
        return False

    is_live = warmup_session.execution_mode in _LIVE_EXECUTION_MODES
    if _pause_if_blocked_by_safety_gate(
        session,
        warmup_session=warmup_session,
        now=now,
        worker_id=worker_id,
    ):
        return True
    if is_live and not adapter.is_available():
        warmup_session.next_micro_session_at = _schedule_within_day(
            now, warmup_session.timezone, rng=rng
        )
        warmup_session.next_step_at = warmup_session.next_micro_session_at
        warmup_session.updated_at = now
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {
                "reason": "passive_disabled",
                "execution_mode": warmup_session.execution_mode,
                "provider": getattr(adapter, "provider_name", "unknown"),
            },
        )
        session.flush()
        return False

    plan_for_day = _resolve_day_plan(warmup_session)
    counters_for_day = _resolve_day_counters(warmup_session)

    pending_actions = _select_actions_for_window(plan_for_day, counters_for_day, rng=rng)

    write_warmup_event(
        session,
        warmup_session,
        "micro_session_window_opened",
        {
            "day": warmup_session.current_day,
            "execution_mode": warmup_session.execution_mode,
            "planned_actions": list(pending_actions),
        },
    )

    performed_actions: list[str] = []
    failed_actions: list[dict[str, Any]] = []

    if pending_actions:
        for action_type in pending_actions:
            action_context: dict[str, Any] = {}
            if is_live:
                resolution = _resolve_action_context(
                    session,
                    warmup_session=warmup_session,
                    action_type=action_type,
                    rng=rng,
                    text_provider=text_provider,
                    now=now,
                )
                if resolution.skip_reason is not None:
                    write_warmup_event(
                        session,
                        warmup_session,
                        "task_skipped",
                        {
                            "day": warmup_session.current_day,
                            "action_type": action_type,
                            "execution_mode": warmup_session.execution_mode,
                            "reason": resolution.skip_reason,
                            "metadata": dict(resolution.metadata),
                        },
                    )
                    continue
                action_context = resolution.context
                if action_type in WRITE_ACTION_TYPES and not adapter.supports_action(action_type):
                    # write-уровень не разрешён конфигом → лог + skip без падения
                    write_warmup_event(
                        session,
                        warmup_session,
                        "task_skipped",
                        {
                            "day": warmup_session.current_day,
                            "action_type": action_type,
                            "execution_mode": warmup_session.execution_mode,
                            "reason": "write_action_not_enabled",
                        },
                    )
                    continue
                result = _execute_live_action(
                    adapter,
                    warmup_session=warmup_session,
                    action_type=action_type,
                    context=action_context,
                )
            else:
                result = WarmupActionResult(
                    status="ok",
                    action_type=action_type,
                    metadata={"simulated": True},
                )
            if not result.is_ok:
                failed_actions.append(
                    {
                        "action_type": action_type,
                        "status": result.status,
                        "error_code": result.error_code,
                        "error_class": result.error_class,
                        "retry_after_seconds": result.retry_after_seconds,
                        "metadata": dict(result.metadata),
                    }
                )
                write_warmup_event(
                    session,
                    warmup_session,
                    "task_failed",
                    {
                        "day": warmup_session.current_day,
                        "action_type": action_type,
                        "execution_mode": warmup_session.execution_mode,
                        "status": result.status,
                        "error_code": result.error_code,
                        "error_class": result.error_class,
                        "retry_after_seconds": result.retry_after_seconds,
                        "metadata": dict(result.metadata),
                    },
                )
                continue
            counters_for_day[action_type] = counters_for_day.get(action_type, 0) + 1
            performed_actions.append(action_type)
            # Phase 4 mutual contact recording for successful p2p_send
            if action_type == "p2p_send" and is_live:
                receiver_account_id = action_context.get("peer_account_id")
                if receiver_account_id:
                    try:
                        contact_summary = record_p2p_contact(
                            session,
                            workspace_id=warmup_session.workspace_id,
                            sender_account_id=warmup_session.account_id,
                            receiver_account_id=str(receiver_account_id),
                            now=now,
                        )
                        write_warmup_event(
                            session,
                            warmup_session,
                            "p2p_contact_recorded",
                            {
                                "day": warmup_session.current_day,
                                "receiver_account_id": receiver_account_id,
                                **contact_summary,
                            },
                        )
                    except ValueError as exc:
                        write_warmup_event(
                            session,
                            warmup_session,
                            "p2p_contact_recording_failed",
                            {
                                "day": warmup_session.current_day,
                                "receiver_account_id": receiver_account_id,
                                "error": str(exc),
                            },
                        )
            write_warmup_event(
                session,
                warmup_session,
                "session_action_executed" if is_live else "session_action_simulated",
                {
                    "day": warmup_session.current_day,
                    "action_type": action_type,
                    "execution_mode": warmup_session.execution_mode,
                    "simulated": not is_live,
                    "metadata": dict(result.metadata),
                },
            )
        if performed_actions:
            warmup_session.daily_counters_json = _persist_day_counters(
                warmup_session.daily_counters_json,
                warmup_session.current_day,
                counters_for_day,
            )
            warmup_session.last_micro_session_at = now
            warmup_session.last_step_at = now
            warmup_session.consecutive_failures = 0
            warmup_session.worker_id = worker_id
            warmup_session.status = WarmupStatus.ACTIVE
            if warmup_session.started_at is None:
                warmup_session.started_at = now
        if failed_actions and not performed_actions:
            warmup_session.worker_id = worker_id
            retry_after_seconds = _max_retry_after_seconds(failed_actions)
            if retry_after_seconds is not None:
                retry_at = now + timedelta(seconds=retry_after_seconds)
                warmup_session.next_attempt_at = retry_at
                warmup_session.next_micro_session_at = retry_at
                warmup_session.next_step_at = retry_at
            error_summary = "; ".join(
                f"{a['action_type']}:{a.get('error_code', 'unknown')}" for a in failed_actions
            )
            breaker_tripped = handle_warmup_step_failure(
                session,
                warmup_session=warmup_session,
                error=error_summary,
                now=now,
                target_status=WarmupStatus.PAUSED_RISK,
            )
            if breaker_tripped:
                warmup_session.next_micro_session_at = None
                warmup_session.next_step_at = None
                write_warmup_event(
                    session,
                    warmup_session,
                    "micro_session_window_closed",
                    {
                        "day": warmup_session.current_day,
                        "performed_actions": performed_actions,
                        "failed_actions": failed_actions,
                        "counters": dict(counters_for_day),
                    },
                )
                session.flush()
                return True
            if retry_after_seconds is not None:
                warmup_session.updated_at = now
                write_warmup_event(
                    session,
                    warmup_session,
                    "micro_session_window_closed",
                    {
                        "day": warmup_session.current_day,
                        "performed_actions": performed_actions,
                        "failed_actions": failed_actions,
                        "counters": dict(counters_for_day),
                    },
                )
                session.flush()
                return True

    write_warmup_event(
        session,
        warmup_session,
        "micro_session_window_closed",
        {
            "day": warmup_session.current_day,
            "performed_actions": performed_actions,
            "failed_actions": failed_actions,
            "counters": dict(counters_for_day),
        },
    )

    day_complete = _is_day_complete(plan_for_day, counters_for_day)
    if day_complete:
        next_day = warmup_session.current_day + 1
        warmup_session.current_day = next_day
        write_warmup_event(
            session,
            warmup_session,
            "day_advanced",
            {"day": next_day, "execution_mode": warmup_session.execution_mode},
        )
        if next_day >= warmup_session.duration_days:
            _complete_dispatch_session(session, warmup_session, now=now)
            session.flush()
            return True
        warmup_session.next_micro_session_at = _next_day_first_window(
            now, warmup_session.timezone, rng=rng
        )
    else:
        warmup_session.next_micro_session_at = _schedule_within_day(
            now, warmup_session.timezone, rng=rng
        )

    warmup_session.next_step_at = warmup_session.next_micro_session_at
    warmup_session.updated_at = now
    session.flush()
    return True


def _pause_if_blocked_by_safety_gate(
    session: Session,
    *,
    warmup_session: WarmupSession,
    now: datetime,
    worker_id: str,
) -> bool:
    verdict = evaluate_safety_gate(
        session,
        workspace_id=warmup_session.workspace_id,
        account_id=warmup_session.account_id,
        intent="warmup",
    )
    if verdict.severity != "blocked":
        return False
    warmup_session.status = WarmupStatus.PAUSED_RISK.value
    warmup_session.next_micro_session_at = None
    warmup_session.next_step_at = None
    warmup_session.worker_id = worker_id
    warmup_session.updated_at = now
    write_warmup_event(
        session,
        warmup_session,
        "warmup_dispatch_blocked_by_gate",
        {"reasons": [reason.model_dump(mode="json") for reason in verdict.reasons]},
    )
    session.flush()
    return True


@dataclass(frozen=True)
class _ActionContextResolution:
    """Result of preparing per-action context before adapter invocation.

    `context` всегда содержит базовые поля (execution_mode, current_day,
    proxy_category). Для write-actions может быть дополнительный
    chat_target/peer_account_id/peer_telegram_user_id/text/text_seed.

    Если контекст недостижим (например, в стратегии нет channels или
    в pool нет eligible peers), `skip_reason` непустой; `context` в
    этом случае нерелевантен и dispatch пишет `task_skipped`.
    """

    context: dict[str, Any]
    skip_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: {})


def _resolve_action_context(
    session: Session,
    *,
    warmup_session: WarmupSession,
    action_type: str,
    rng: random.Random,
    text_provider: WarmupTextProvider,
    now: datetime,
) -> _ActionContextResolution:
    """Подготовка детерминированного context для action.

    seed для текстовых артефактов = sha256(session_id|day|action_type) →
    одинаковая стратегия + один день дают один и тот же текст между
    рестартами. Это требование Phase 0a: антифрод-сигналы должны быть
    воспроизводимы между логами.
    """
    proxy_snapshot = warmup_session.proxy_snapshot_json or {}
    base: dict[str, Any] = {
        "execution_mode": warmup_session.execution_mode,
        "current_day": warmup_session.current_day,
        "proxy_category": proxy_snapshot.get("proxy_category"),
    }
    if action_type == "join_chat":
        chat_target = _select_chat_target(warmup_session, rng=rng)
        if chat_target is None:
            return _ActionContextResolution(
                context=base, skip_reason="no_target_channels_configured"
            )
        return _ActionContextResolution(context={**base, "chat_target": chat_target})
    if action_type == "p2p_send":
        peer = select_eligible_peer(
            session,
            workspace_id=warmup_session.workspace_id,
            sender_account_id=warmup_session.account_id,
            now=now,
        )
        if peer is None:
            return _ActionContextResolution(context=base, skip_reason="no_eligible_trusted_peers")
        text_seed = _derive_text_seed(warmup_session, action_type)
        if not text_provider.is_available():
            return _ActionContextResolution(
                context=base,
                skip_reason="text_provider_unavailable",
                metadata={"provider": getattr(text_provider, "provider_name", "unknown")},
            )
        rendered = text_provider.compose_p2p_message(
            TextVariationRequest(template="", seed=text_seed)
        )
        if not rendered.rendered:
            return _ActionContextResolution(
                context=base,
                skip_reason="text_provider_empty_render",
                metadata={"provider": rendered.provider},
            )
        return _ActionContextResolution(
            context={
                **base,
                "peer_account_id": peer.account_id,
                "peer_telegram_user_id": peer.telegram_user_id,
                "peer_row_id": peer.peer_row_id,
                "text": rendered.rendered,
                "text_seed": text_seed,
                "text_provider": rendered.provider,
            }
        )
    return _ActionContextResolution(context=base)


def _select_chat_target(warmup_session: WarmupSession, *, rng: random.Random) -> str | None:
    """Pick одно публичное channel-username из strategy.target_channels_json."""
    targets = warmup_session.strategy.target_channels_json or []
    candidates: list[str] = []
    for entry in targets:
        value = entry.get("username") or entry.get("chat_username") or entry.get("target")
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    if not candidates:
        return None
    return candidates[rng.randint(0, len(candidates) - 1)]


def _derive_text_seed(warmup_session: WarmupSession, action_type: str) -> str:
    raw = f"{warmup_session.id}|{warmup_session.current_day}|{action_type}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _execute_live_action(
    adapter: WarmupTdlibAdapter,
    *,
    warmup_session: WarmupSession,
    action_type: str,
    context: dict[str, Any],
) -> WarmupActionResult:
    """Invoke the live adapter; convert exceptions to network_error.

    Контракт адаптера запрещает исключения, но мы держим защиту, чтобы
    кривая реализация не валила воркер.
    """
    try:
        return adapter.execute_action(
            account_id=warmup_session.account_id,
            action_type=action_type,
            context=context,
        )
    except Exception as exc:  # defensive
        return WarmupActionResult(
            status="network_error",
            action_type=action_type,
            error_code="adapter_raised",
            error_class=exc.__class__.__name__,
            metadata={"exception_message": str(exc)[:200]},
        )


def _complete_dispatch_session(
    session: Session, warmup_session: WarmupSession, *, now: datetime
) -> None:
    warmup_session.status = WarmupStatus.COMPLETED
    warmup_session.completed_at = now
    warmup_session.next_step_at = None
    warmup_session.next_micro_session_at = None
    warmup_session.updated_at = now
    write_warmup_event(
        session,
        warmup_session,
        "completed",
        {"day": warmup_session.current_day, "execution_mode": warmup_session.execution_mode},
    )
    if release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=_isolation_owner(warmup_session.id),
    ):
        write_warmup_event(
            session,
            warmup_session,
            "isolation_released",
            {"reason": "session_completed"},
        )


def _max_retry_after_seconds(failed_actions: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for action in failed_actions:
        raw = action.get("retry_after_seconds")
        if raw is None:
            continue
        try:
            values.append(max(0, int(raw)))
        except TypeError, ValueError:
            continue
    return max(values) if values else None


def _resolve_day_plan(warmup_session: WarmupSession) -> dict[str, int]:
    """Read daily_action_limits for the current day from the strategy snapshot.

    Contract: strategy daily_action_limits uses **1-based** day keys
    (``"1"``, ``"2"``, …). ``WarmupSession.current_day`` is 0-based, so we
    look up ``current_day + 1``.  Fallback to ``current_day`` key exists
    only for backward compatibility with legacy strategies that may have
    used 0-based keys — it will never match for correctly-seeded data.
    """
    limits = warmup_session.strategy.daily_action_limits_json or {}
    raw = limits.get(str(warmup_session.current_day + 1)) or limits.get(
        str(warmup_session.current_day)
    )
    if not isinstance(raw, dict):
        return {}
    plan: dict[str, int] = {}
    raw_items = cast(dict[object, object], raw)
    for key, value in raw_items.items():
        try:
            plan[str(key)] = max(0, int(cast(Any, value)))
        except TypeError, ValueError:
            continue
    return plan


def _resolve_day_counters(warmup_session: WarmupSession) -> dict[str, int]:
    counters = warmup_session.daily_counters_json or {}
    raw = counters.get(str(warmup_session.current_day))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    raw_items = cast(dict[object, object], raw)
    for key, value in raw_items.items():
        try:
            out[str(key)] = max(0, int(cast(Any, value)))
        except TypeError, ValueError:
            continue
    return out


def _persist_day_counters(
    counters_json: dict[str, Any] | None,
    current_day: int,
    counters_for_day: dict[str, int],
) -> dict[str, Any]:
    counters = dict(counters_json or {})
    counters[str(current_day)] = dict(counters_for_day)
    return counters


def _select_actions_for_window(
    plan: dict[str, int],
    counters: dict[str, int],
    *,
    rng: random.Random,
) -> list[str]:
    """Pick which actions are simulated in this micro-session window.

    Conservative: at most one of each action type per window, capped at
    MAX_ACTIONS_PER_MICRO_SESSION. Action types ordered by
    DEFAULT_ACTION_PRIORITY first, then alphabetically for stability.
    """
    candidates = sorted(
        plan.keys(),
        key=lambda key: (
            DEFAULT_ACTION_PRIORITY.index(key)
            if key in DEFAULT_ACTION_PRIORITY
            else len(DEFAULT_ACTION_PRIORITY),
            key,
        ),
    )
    chosen: list[str] = []
    for key in candidates:
        if len(chosen) >= MAX_ACTIONS_PER_MICRO_SESSION:
            break
        budget = plan.get(key, 0) - counters.get(key, 0)
        if budget <= 0:
            continue
        # pick this action with small probabilistic drop to introduce jitter
        if rng.random() < 0.85:
            chosen.append(key)
    return chosen


def _is_day_complete(plan: dict[str, int], counters: dict[str, int]) -> bool:
    if not plan:
        return True
    for key, total in plan.items():
        if counters.get(key, 0) < total:
            return False
    return True


def _schedule_within_day(
    now: datetime, timezone_name: str | None, *, rng: random.Random
) -> datetime:
    span_min = max(1, settings.warmup_micro_session_min_minutes)
    span_max = max(span_min, settings.warmup_micro_session_max_minutes)
    # space windows out: jitter from one-window-length to several-window-lengths
    jitter_minutes = rng.randint(span_min * 6, span_max * 12)
    candidate = now + timedelta(minutes=jitter_minutes)
    if _is_in_quiet_hours(candidate, timezone_name):
        return _next_quiet_hours_end(candidate, timezone_name)
    return candidate


def _next_day_first_window(
    now: datetime, timezone_name: str | None, *, rng: random.Random
) -> datetime:
    base = now + timedelta(hours=12)
    jitter_minutes = rng.randint(0, 180)
    candidate = base + timedelta(minutes=jitter_minutes)
    if _is_in_quiet_hours(candidate, timezone_name):
        return _next_quiet_hours_end(candidate, timezone_name)
    return candidate


def _is_in_quiet_hours(moment: datetime, timezone_name: str | None) -> bool:
    local_hour = _local_hour(moment, timezone_name)
    return _is_hour_in_quiet_window(
        local_hour,
        settings.warmup_quiet_hours_local_start,
        settings.warmup_quiet_hours_local_end,
    )


def _is_hour_in_quiet_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # wraps midnight, e.g. 23 → 8
    return hour >= start or hour < end


def _next_quiet_hours_end(moment: datetime, timezone_name: str | None) -> datetime:
    """Return earliest UTC datetime strictly after `moment` whose local hour
    matches `warmup_quiet_hours_local_end` (i.e. quiet hours ended)."""
    tz = _resolve_timezone(timezone_name)
    local_now = moment.astimezone(tz)
    end_hour = settings.warmup_quiet_hours_local_end
    candidate_local = local_now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if candidate_local <= local_now:
        candidate_local = candidate_local + timedelta(days=1)
    # Combine with date+end_hour ensures tz dst safety for our purposes
    candidate_local = datetime.combine(candidate_local.date(), time(hour=end_hour), tzinfo=tz)
    if candidate_local <= local_now:
        candidate_local = candidate_local + timedelta(days=1)
    return candidate_local.astimezone(UTC)


def _local_hour(moment: datetime, timezone_name: str | None) -> int:
    tz = _resolve_timezone(timezone_name)
    return moment.astimezone(tz).hour


def _resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")
    return ZoneInfo("UTC")
