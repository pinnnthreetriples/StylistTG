from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.warmup import read_models, repository
from app.modules.warmup.contracts import (
    WarmupEventPageRead,
    WarmupLiveEventPageRead,
    WarmupIsolationStatusRead,
    WarmupReadinessRead,
    WarmupSessionPageRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupStrategyRead,
    WarmupValidateRead,
)
from app.modules.warmup.isolation import get_claim
from app.modules.warmup.policies import warmup_operation_policy as _warmup_operation_policy
from app.modules.warmup.readiness import validate_warmup_readiness
from app.services.redis_client import redis_from_url


def get_warmup_readiness(session: Session, *, workspace_id: str) -> WarmupReadinessRead:
    return WarmupReadinessRead(
        workers_enabled=settings.warmup_workers_enabled,
        dry_run=settings.warmup_dry_run,
        redis_connected=_redis_connected(),
        database_connected=True,
        active_sessions=repository.count_active_sessions(session, workspace_id=workspace_id),
        strategies_available=repository.count_available_strategies(
            session, workspace_id=workspace_id
        ),
    )


def validate_warmup(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
) -> WarmupValidateRead:
    return validate_warmup_readiness(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )


def list_warmup_strategies(session: Session, *, workspace_id: str) -> list[WarmupStrategyRead]:
    return [
        read_models.strategy_read(strategy)
        for strategy in repository.list_available_strategies(session, workspace_id=workspace_id)
    ]


def list_warmup_sessions_page(
    session: Session,
    *,
    workspace_id: str,
    statuses: list[str] | None,
    page: int,
    limit: int,
) -> WarmupSessionPageRead:
    items, total = repository.list_warmup_sessions(
        session,
        workspace_id=workspace_id,
        statuses=statuses,
        page=page,
        limit=limit,
    )
    return WarmupSessionPageRead(
        items=[read_models.session_summary(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


def get_warmup_session_detail(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    return read_models.session_read(
        repository.get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    )


def get_warmup_session_status(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionStatusRead:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    return read_models.session_status_read(warmup_session)


def list_warmup_session_events_page(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    page: int,
    limit: int,
) -> WarmupEventPageRead:
    items, total = repository.list_warmup_events(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        page=page,
        limit=limit,
    )
    return read_models.event_page_read(items, total=total, page=page, limit=limit)


def list_warmup_event_feed_page(
    session: Session,
    *,
    workspace_id: str,
    account_id: str | None,
    severities: list[str] | None,
    cursor: str | None,
    limit: int,
    include_accounts: bool = True,
) -> WarmupLiveEventPageRead:
    normalized = _normalize_severities(severities)
    items, total = repository.list_warmup_event_feed(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        severities=normalized,
        cursor=cursor,
        limit=limit,
    )
    accounts = (
        repository.list_warmup_event_accounts(session, workspace_id=workspace_id)
        if include_accounts
        else []
    )
    return read_models.live_event_page_read(items, accounts=accounts, total=total, limit=limit)


def _normalize_severities(severities: list[str] | None) -> list[str] | None:
    if not severities:
        return None
    allowed = {"info", "success", "warning", "error", "debug"}
    normalized = sorted({severity for severity in severities if severity in allowed})
    return normalized or None


def get_warmup_isolation_status(session: Session, *, account_id: str) -> WarmupIsolationStatusRead:
    return read_models.isolation_status_read(get_claim(session, account_id=account_id))


def warmup_operation_policy(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    operation: str,
) -> dict[str, Any]:
    return _warmup_operation_policy(
        warmup_session=repository.active_warmup_for_account(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
        ),
        operation=operation,
    )


def _redis_connected() -> bool:
    try:
        client = redis_from_url(socket_connect_timeout=0.2)
        try:
            return bool(cast(Any, client).ping())
        finally:
            client.close()
    except Exception:
        return False


__all__ = [
    "get_warmup_isolation_status",
    "get_warmup_readiness",
    "get_warmup_session_detail",
    "get_warmup_session_status",
    "list_warmup_event_feed_page",
    "list_warmup_session_events_page",
    "list_warmup_sessions_page",
    "list_warmup_strategies",
    "validate_warmup",
    "warmup_operation_policy",
]
