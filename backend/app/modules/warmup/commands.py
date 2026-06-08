from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS
from app.config import settings
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus, new_id
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.account_shared.interfaces import lookup_account
from app.modules.account_survival import events as survival_events
from app.modules.warmup import read_models, repository
from app.modules.warmup.contracts import WarmupSessionRead
from app.modules.warmup.cold_soak import compute_cold_soak_window
from app.modules.warmup.enqueue import enqueue_warmup_dispatch_tick, enqueue_warmup_due_sessions
from app.modules.warmup.errors import (
    WarmupIsolationConflictError,
    WarmupQueueUnavailableError,
    WarmupSessionRejectedError,
)
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import acquire_claim, release_claim
from app.modules.warmup.p2p_graph import assign_friends
from app.modules.warmup.policies import (
    can_create_warmup_session,
    is_live_warmup_mode,
    validate_session_status_transition,
)
from app.modules.warmup.readiness import validate_warmup_readiness


def create_warmup_session(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    readiness = validate_warmup_readiness(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )
    can_create_warmup_session(readiness.blocking_reasons)

    timestamp = now or datetime.now(UTC)
    account = lookup_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise WarmupSessionRejectedError("account not found")
    strategy = repository.get_strategy(session, strategy_id=strategy_id)
    execution_mode = (
        strategy.execution_mode if strategy is not None else WarmupExecutionMode.DRY_RUN.value
    )
    duration_days = (
        strategy.duration_days if strategy is not None else settings.warmup_default_duration_days
    )
    proxy_snapshot = _build_proxy_snapshot(session, account_id=account_id)
    cold_soak_until = compute_cold_soak_window(strategy, timestamp)

    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=WarmupStatus.COLD_SOAK,
        current_day=0,
        cadence_hours=settings.warmup_default_cadence_hours,
        cold_soak_until=cold_soak_until,
        next_step_at=cold_soak_until,
        next_micro_session_at=cold_soak_until if is_live_warmup_mode(execution_mode) else None,
        execution_mode=execution_mode,
        duration_days=duration_days,
        proxy_snapshot_json=proxy_snapshot,
    )
    session.add(warmup_session)
    session.flush()
    advance(
        session,
        account,
        to_state=AccountLifecycleState.COLD_SOAK,
        now=timestamp,
        reason="warmup_session_created",
        metadata={"warmup_session_id": warmup_session.id, "strategy_id": strategy_id},
    )
    write_warmup_event(
        session,
        warmup_session,
        "session_created",
        {
            "status": WarmupStatus.COLD_SOAK.value,
            "strategy_id": strategy_id,
            "execution_mode": execution_mode,
            "duration_days": duration_days,
            "proxy_snapshot": proxy_snapshot,
        },
    )
    write_warmup_event(
        session,
        warmup_session,
        "cold_soak_started",
        {
            "until": cold_soak_until.isoformat(),
            "strategy_name": strategy.name if strategy is not None else None,
        },
    )
    survival_events.on_warmup_started(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
        now=timestamp,
        strategy_id=strategy_id,
        strategy_name=strategy.name if strategy is not None else None,
    )
    assign_friends(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
        now=timestamp,
    )
    if is_live_warmup_mode(execution_mode):
        owner = f"warmup:{warmup_session.id}"
        claim_acquired = acquire_claim(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            held_by=owner,
            reason=f"warmup execution_mode={execution_mode}",
            now=timestamp,
        )
        if not claim_acquired:
            raise WarmupIsolationConflictError()
        write_warmup_event(
            session,
            warmup_session,
            "isolation_claimed",
            {"held_by": owner, "execution_mode": execution_mode},
        )
    return warmup_session


def create_warmup_session_use_case(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    warmup_session = create_warmup_session(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )
    session.commit()
    session.refresh(warmup_session)
    enqueue_ok = True
    if settings.warmup_workers_enabled:
        enqueue_ok = (
            enqueue_warmup_due_sessions()
            if warmup_session.execution_mode == WarmupExecutionMode.DRY_RUN.value
            else enqueue_warmup_dispatch_tick()
        )
    if enqueue_ok is False:
        warmup_session.status = WarmupStatus.FAILED
        write_warmup_event(session, warmup_session, "queue_enqueue_failed", {})
        release_claim(
            session,
            account_id=warmup_session.account_id,
            held_by=f"warmup:{warmup_session.id}",
        )
        session.commit()
        raise WarmupQueueUnavailableError()
    return read_models.session_read(warmup_session)


def pause_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    reason: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    validate_session_status_transition(action="pause", current_status=warmup_session.status)
    timestamp = now or datetime.now(UTC)
    warmup_session.status = WarmupStatus.PAUSED_MANUAL
    warmup_session.paused_at = timestamp
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "paused", {"reason": reason})
    return warmup_session


def pause_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    reason: str,
) -> WarmupSessionRead:
    warmup_session = pause_warmup_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        reason=reason,
    )
    session.commit()
    session.refresh(warmup_session)
    return read_models.session_read(warmup_session)


def resume_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    timestamp = now or datetime.now(UTC)
    validate_session_status_transition(
        action="resume",
        current_status=warmup_session.status,
        next_attempt_at=warmup_session.next_attempt_at,
        now=timestamp,
    )
    warmup_session.status = WarmupStatus.SCHEDULED
    warmup_session.paused_at = None
    warmup_session.consecutive_failures = 0
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "resumed", {})
    return warmup_session


def resume_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    warmup_session = resume_warmup_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
    )
    session.commit()
    session.refresh(warmup_session)
    return read_models.session_read(warmup_session)


def set_disabled_actions(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    actions: list[str],
    actor_user_id: str | None = None,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    timestamp = now or datetime.now(UTC)
    disabled_actions = _normalize_disabled_actions(actions)
    _validate_disabled_actions_leave_enabled_action(warmup_session, disabled_actions)
    previous_actions = list(warmup_session.disabled_actions_json or [])
    warmup_session.disabled_actions_json = disabled_actions
    warmup_session.updated_at = timestamp
    write_warmup_event(
        session,
        warmup_session,
        "disabled_actions_updated",
        {
            "previous_actions": previous_actions,
            "disabled_actions": disabled_actions,
            "actor_user_id": actor_user_id,
        },
    )
    return warmup_session


def set_disabled_actions_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    actions: list[str],
    actor_user_id: str | None = None,
) -> WarmupSessionRead:
    warmup_session = set_disabled_actions(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        actions=actions,
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(warmup_session)
    return read_models.session_read(warmup_session)


def delete_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> None:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=f"warmup:{warmup_session.id}",
    )
    session.delete(warmup_session)


def delete_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> None:
    delete_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    session.commit()


def _build_proxy_snapshot(session: Session, *, account_id: str) -> dict[str, Any] | None:
    """Return the safe AccountProxy snapshot captured at session creation."""
    proxy = repository.get_account_proxy_snapshot_source(session, account_id=account_id)
    if proxy is None:
        return None
    return {
        "proxy_type": proxy.proxy_type,
        "proxy_category": proxy.proxy_category,
        "host": proxy.host,
        "port": proxy.port,
        "status": proxy.status,
        "last_checked_at": (
            proxy.last_checked_at.isoformat() if proxy.last_checked_at is not None else None
        ),
    }


def _normalize_disabled_actions(actions: list[str]) -> list[str]:
    requested = {action.strip() for action in actions if action.strip()}
    supported = list(SUPPORTED_ADVANCED_ACTIONS)
    unknown = sorted(requested - set(supported))
    if unknown:
        raise WarmupSessionRejectedError(f"unknown disabled action: {unknown[0]}")
    return [action for action in supported if action in requested]


def _validate_disabled_actions_leave_enabled_action(
    warmup_session: WarmupSession, disabled_actions: list[str]
) -> None:
    planned_actions = _planned_action_types(warmup_session.strategy.daily_action_limits_json or {})
    action_pool = planned_actions or set(SUPPORTED_ADVANCED_ACTIONS)
    if action_pool and action_pool.issubset(set(disabled_actions)):
        raise WarmupSessionRejectedError("at least one warmup action must remain enabled")


def _planned_action_types(daily_action_limits: dict[str, Any]) -> set[str]:
    planned: set[str] = set()
    for limits in daily_action_limits.values():
        if not isinstance(limits, dict):
            continue
        typed_limits = cast(dict[Any, Any], limits)
        for action_type, limit in typed_limits.items():
            if isinstance(action_type, str) and isinstance(limit, int | float) and limit > 0:
                planned.add(action_type)
    return planned


__all__ = [
    "_build_proxy_snapshot",
    "create_warmup_session",
    "create_warmup_session_use_case",
    "delete_warmup_session",
    "delete_warmup_session_use_case",
    "pause_warmup_session",
    "pause_warmup_session_use_case",
    "resume_warmup_session",
    "resume_warmup_session_use_case",
    "set_disabled_actions",
    "set_disabled_actions_use_case",
]
