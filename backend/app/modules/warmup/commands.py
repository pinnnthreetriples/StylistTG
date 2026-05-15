from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus, new_id
from app.modules.warmup import read_models, repository
from app.modules.warmup.contracts import WarmupSessionRead
from app.modules.warmup.enqueue import enqueue_warmup_dispatch_tick, enqueue_warmup_due_sessions
from app.modules.warmup.errors import WarmupIsolationConflictError, WarmupQueueUnavailableError
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import acquire_claim, release_claim
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
    strategy = repository.get_strategy(session, strategy_id=strategy_id)
    execution_mode = (
        strategy.execution_mode if strategy is not None else WarmupExecutionMode.DRY_RUN.value
    )
    duration_days = (
        strategy.duration_days if strategy is not None else settings.warmup_default_duration_days
    )
    proxy_snapshot = _build_proxy_snapshot(session, account_id=account_id)

    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=WarmupStatus.SCHEDULED,
        current_day=0,
        cadence_hours=settings.warmup_default_cadence_hours,
        next_step_at=timestamp,
        next_micro_session_at=timestamp if is_live_warmup_mode(execution_mode) else None,
        execution_mode=execution_mode,
        duration_days=duration_days,
        proxy_snapshot_json=proxy_snapshot,
    )
    session.add(warmup_session)
    session.flush()
    write_warmup_event(
        session,
        warmup_session,
        "session_created",
        {
            "status": WarmupStatus.SCHEDULED.value,
            "strategy_id": strategy_id,
            "execution_mode": execution_mode,
            "duration_days": duration_days,
            "proxy_snapshot": proxy_snapshot,
        },
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
]
