from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ACTIVE_WARMUP_STATUSES,
    Account,
    AccountProxy,
    WarmupEvent,
    WarmupSession,
    WarmupStrategy,
)
from app.modules.warmup.errors import WarmupSessionNotFoundError


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
        raise WarmupSessionNotFoundError()
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


def list_warmup_event_feed(
    session: Session,
    *,
    workspace_id: str,
    account_id: str | None = None,
    severities: list[str] | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> tuple[list[WarmupEvent], int]:
    filters = [WarmupEvent.workspace_id == workspace_id]
    if account_id:
        filters.append(WarmupSession.account_id == account_id)
    if severities:
        filters.append(WarmupEvent.severity.in_(severities))

    cursor_event = session.get(WarmupEvent, cursor) if cursor else None
    if cursor_event is not None and cursor_event.workspace_id == workspace_id:
        filters.append(
            or_(
                WarmupEvent.created_at > cursor_event.created_at,
                (WarmupEvent.created_at == cursor_event.created_at)
                & (WarmupEvent.id > cursor_event.id),
            )
        )

    base = (
        select(WarmupEvent)
        .join(WarmupEvent.session)
        .join(WarmupSession.account)
        .where(*filters)
    )
    total = int(session.scalar(select(func.count()).select_from(base.subquery())) or 0)

    if cursor_event is None:
        latest = list(
            session.execute(
                base.options(
                    joinedload(WarmupEvent.session).joinedload(WarmupSession.account)
                )
                .order_by(WarmupEvent.created_at.desc(), WarmupEvent.id.desc())
                .limit(limit)
            ).scalars()
        )
        latest.reverse()
        return latest, total

    items = list(
        session.execute(
            base.options(joinedload(WarmupEvent.session).joinedload(WarmupSession.account))
            .order_by(WarmupEvent.created_at.asc(), WarmupEvent.id.asc())
            .limit(limit)
        ).scalars()
    )
    return items, total


def list_warmup_event_accounts(
    session: Session,
    *,
    workspace_id: str,
) -> list[Account]:
    return list(
        session.execute(
            select(Account)
            .join(WarmupSession, WarmupSession.account_id == Account.id)
            .join(WarmupEvent, WarmupEvent.session_id == WarmupSession.id)
            .where(WarmupEvent.workspace_id == workspace_id)
            .distinct()
            .order_by(Account.external_ref.asc())
        ).scalars()
    )


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
    for warmup_session in rows:
        if warmup_session.account_id not in result:
            result[warmup_session.account_id] = warmup_session
    return result


def get_strategy(session: Session, *, strategy_id: str) -> WarmupStrategy | None:
    return session.get(WarmupStrategy, strategy_id)


def list_available_strategies(
    session: Session,
    *,
    workspace_id: str,
) -> list[WarmupStrategy]:
    return list(
        session.execute(
            select(WarmupStrategy)
            .where(
                (WarmupStrategy.workspace_id == workspace_id)
                | (WarmupStrategy.workspace_id.is_(None))
            )
            .order_by(WarmupStrategy.is_preset.desc(), WarmupStrategy.name.asc())
        ).scalars()
    )


def count_active_sessions(session: Session, *, workspace_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(WarmupSession)
            .where(
                WarmupSession.workspace_id == workspace_id,
                WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
            )
        )
        or 0
    )


def count_available_strategies(session: Session, *, workspace_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(WarmupStrategy)
            .where(
                (WarmupStrategy.workspace_id == workspace_id)
                | (WarmupStrategy.workspace_id.is_(None))
            )
        )
        or 0
    )


def get_account_proxy_snapshot_source(
    session: Session,
    *,
    account_id: str,
) -> AccountProxy | None:
    return session.get(AccountProxy, account_id)


__all__ = [
    "active_warmup_for_account",
    "batch_active_warmups_for_accounts",
    "count_active_sessions",
    "count_available_strategies",
    "get_account_proxy_snapshot_source",
    "get_strategy",
    "get_warmup_session",
    "list_warmup_event_accounts",
    "list_warmup_event_feed",
    "list_available_strategies",
    "list_warmup_events",
    "list_warmup_sessions",
]
