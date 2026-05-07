from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ACTIVE_WARMUP_STATUSES, WarmupEvent, WarmupSession, WarmupStatus, new_id
from app.services.warmup_readiness import validate_warmup_readiness


SENSITIVE_EVENT_KEYS = {
    "api_hash",
    "api_key",
    "auth_key",
    "password",
    "proxy_password",
    "session",
    "session_string",
    "tdlib_path",
}


def write_warmup_event(
    session: Session,
    warmup_session: WarmupSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> WarmupEvent:
    event = WarmupEvent(
        id=new_id(),
        workspace_id=warmup_session.workspace_id,
        session_id=warmup_session.id,
        event_type=event_type,
        payload_json=_sanitize_event_payload(payload or {}),
    )
    session.add(event)
    return event


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
    if not readiness.is_ready:
        raise ValueError("; ".join(readiness.blocking_reasons))

    timestamp = now or datetime.now(UTC)
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=WarmupStatus.SCHEDULED,
        current_day=0,
        cadence_hours=settings.warmup_default_cadence_hours,
        next_step_at=timestamp,
    )
    session.add(warmup_session)
    session.flush()
    write_warmup_event(
        session,
        warmup_session,
        "session_created",
        {"status": WarmupStatus.SCHEDULED.value, "strategy_id": strategy_id},
    )
    return warmup_session


def get_warmup_session(session: Session, *, session_id: str, workspace_id: str) -> WarmupSession:
    warmup_session = session.execute(
        select(WarmupSession).where(
            WarmupSession.id == session_id,
            WarmupSession.workspace_id == workspace_id,
        )
    ).scalars().first()
    if warmup_session is None:
        raise ValueError("session not found")
    return warmup_session


def list_warmup_sessions(
    session: Session,
    *,
    workspace_id: str,
    statuses: list[str] | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[WarmupSession], int]:
    query = select(WarmupSession).where(WarmupSession.workspace_id == workspace_id)
    count_query = select(func.count()).select_from(WarmupSession).where(WarmupSession.workspace_id == workspace_id)
    if statuses:
        query = query.where(WarmupSession.status.in_(statuses))
        count_query = count_query.where(WarmupSession.status.in_(statuses))
    total = int(session.scalar(count_query) or 0)
    items = list(
        session.execute(
            query.order_by(WarmupSession.updated_at.desc())
            .offset((max(page, 1) - 1) * limit)
            .limit(limit)
        ).scalars()
    )
    return items, total


def list_warmup_events(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[WarmupEvent], int]:
    get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    query = select(WarmupEvent).where(
        WarmupEvent.session_id == session_id,
        WarmupEvent.workspace_id == workspace_id,
    )
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = list(
        session.execute(
            query.order_by(WarmupEvent.created_at.desc())
            .offset((max(page, 1) - 1) * limit)
            .limit(limit)
        ).scalars()
    )
    return items, total


def pause_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    reason: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    if warmup_session.status not in {WarmupStatus.SCHEDULED, WarmupStatus.ACTIVE}:
        raise ValueError("session cannot be paused")
    timestamp = now or datetime.now(UTC)
    warmup_session.status = WarmupStatus.PAUSED_MANUAL
    warmup_session.paused_at = timestamp
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "paused", {"reason": reason})
    return warmup_session


def resume_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    if warmup_session.status not in {WarmupStatus.PAUSED_MANUAL, WarmupStatus.PAUSED_RISK}:
        raise ValueError("session cannot be resumed")
    timestamp = now or datetime.now(UTC)
    if warmup_session.next_attempt_at and warmup_session.next_attempt_at > timestamp:
        raise ValueError(f"retry_not_ready:{warmup_session.next_attempt_at.isoformat()}")
    warmup_session.status = WarmupStatus.SCHEDULED
    warmup_session.paused_at = None
    warmup_session.consecutive_failures = 0
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "resumed", {})
    return warmup_session


def delete_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> None:
    warmup_session = get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    session.delete(warmup_session)


def is_warmup_active_status(status: str) -> bool:
    return status in {item.value for item in ACTIVE_WARMUP_STATUSES}


def active_warmup_for_account(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> WarmupSession | None:
    return session.execute(
        select(WarmupSession)
        .where(
            WarmupSession.workspace_id == workspace_id,
            WarmupSession.account_id == account_id,
            WarmupSession.status.in_([status.value for status in ACTIVE_WARMUP_STATUSES]),
        )
        .order_by(WarmupSession.updated_at.desc())
        .limit(1)
    ).scalars().first()


def warmup_operation_policy(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    operation: str,
) -> dict[str, Any]:
    warmup_session = active_warmup_for_account(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    locked_operations = {"profile_update", "proxy_change", "account_delete"}
    is_locked = warmup_session is not None and operation in locked_operations
    return {
        "session_id": warmup_session.id if warmup_session else None,
        "status": warmup_session.status if warmup_session else None,
        "current_day": warmup_session.current_day if warmup_session else None,
        "is_locked": is_locked,
        "reason": "Аккаунт находится в подготовке" if is_locked else None,
    }


def _sanitize_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_EVENT_KEYS:
            sanitized[key] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_event_payload(value)
        else:
            sanitized[key] = value
    return sanitized
