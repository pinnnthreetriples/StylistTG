from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    ACTIVE_WARMUP_STATUSES,
    AccountProxy,
    WarmupEvent,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import acquire_claim, release_claim
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
    if not readiness.is_ready:
        raise ValueError("; ".join(readiness.blocking_reasons))

    timestamp = now or datetime.now(UTC)
    strategy = session.get(WarmupStrategy, strategy_id)
    execution_mode = (
        strategy.execution_mode if strategy is not None else WarmupExecutionMode.DRY_RUN.value
    )
    duration_days = (
        strategy.duration_days if strategy is not None else settings.warmup_default_duration_days
    )
    proxy_snapshot = _build_proxy_snapshot(session, account_id=account_id)

    is_live_mode = execution_mode != WarmupExecutionMode.DRY_RUN.value
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=WarmupStatus.SCHEDULED,
        current_day=0,
        cadence_hours=settings.warmup_default_cadence_hours,
        next_step_at=timestamp,
        next_micro_session_at=timestamp if is_live_mode else None,
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
    if is_live_mode:
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
            raise ValueError("account is already isolated by another warmup session")
        write_warmup_event(
            session,
            warmup_session,
            "isolation_claimed",
            {"held_by": owner, "execution_mode": execution_mode},
        )
    return warmup_session


def _build_proxy_snapshot(session: Session, *, account_id: str) -> dict[str, Any] | None:
    """Снимок AccountProxy на момент создания сессии.

    Никаких credentials в snapshot не попадает — только маршрутные поля,
    необходимые будущему live-движку для аудита и решений (geo-match,
    datacenter-policy). Возвращает None если у аккаунта нет настроенного
    прокси.
    """
    proxy = session.get(AccountProxy, account_id)
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


def get_warmup_session(session: Session, *, session_id: str, workspace_id: str) -> WarmupSession:
    warmup_session = (
        session.execute(
            select(WarmupSession)
            .where(
                WarmupSession.id == session_id,
                WarmupSession.workspace_id == workspace_id,
            )
            .options(
                joinedload(WarmupSession.account),
                joinedload(WarmupSession.strategy),
            )
        )
        .scalars()
        .first()
    )
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
    query = (
        select(WarmupSession)
        .where(WarmupSession.workspace_id == workspace_id)
        .options(
            joinedload(WarmupSession.account),
            joinedload(WarmupSession.strategy),
        )
    )
    count_query = (
        select(func.count())
        .select_from(WarmupSession)
        .where(WarmupSession.workspace_id == workspace_id)
    )
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
    release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=f"warmup:{warmup_session.id}",
    )
    session.delete(warmup_session)


def is_warmup_active_status(status: str) -> bool:
    return status in {item.value for item in ACTIVE_WARMUP_STATUSES}


def active_warmup_for_account(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> WarmupSession | None:
    return (
        session.execute(
            select(WarmupSession)
            .where(
                WarmupSession.workspace_id == workspace_id,
                WarmupSession.account_id == account_id,
                WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
            )
            .order_by(WarmupSession.updated_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def batch_active_warmups_for_accounts(
    session: Session,
    *,
    account_ids: list[str],
    workspace_id: str,
) -> dict[str, WarmupSession]:
    """Return {account_id: WarmupSession} for all accounts with active warmup."""
    if not account_ids:
        return {}
    rows = (
        session.execute(
            select(WarmupSession)
            .where(
                WarmupSession.workspace_id == workspace_id,
                WarmupSession.account_id.in_(account_ids),
                WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
            )
            .order_by(WarmupSession.updated_at.desc())
        )
        .scalars()
        .all()
    )
    result: dict[str, WarmupSession] = {}
    for ws in rows:
        if ws.account_id not in result:
            result[ws.account_id] = ws
    return result


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
