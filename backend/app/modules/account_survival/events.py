from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.modules.account_survival import repository

logger = logging.getLogger(__name__)


def on_account_imported(
    session: Session, *, account_id: str, workspace_id: str, now: datetime
) -> None:
    _safe(
        "account_imported",
        lambda: repository.ensure_metric(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            imported_at=now,
            now=now,
        ),
    )


def on_warmup_started(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
    strategy_id: str | None,
    strategy_name: str | None,
) -> None:
    _safe(
        "warmup_started",
        lambda: repository.mark_warmup_started(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            now=now,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
        ),
    )


def on_warmup_completed(
    session: Session, *, account_id: str, workspace_id: str, now: datetime
) -> None:
    _safe(
        "warmup_completed",
        lambda: repository.mark_warmup_completed(
            session, workspace_id=workspace_id, account_id=account_id, now=now
        ),
    )


def on_account_frozen(
    session: Session, *, account_id: str, workspace_id: str, now: datetime
) -> None:
    _safe(
        "account_frozen",
        lambda: repository.mark_freeze(
            session, workspace_id=workspace_id, account_id=account_id, now=now
        ),
    )


def on_account_terminal(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    terminal_status: str,
    now: datetime,
) -> None:
    _safe(
        "account_terminal",
        lambda: repository.mark_terminal(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            terminal_status=terminal_status,
            now=now,
        ),
    )


def on_flood_wait(session: Session, *, account_id: str, workspace_id: str, now: datetime) -> None:
    _safe(
        "flood_wait",
        lambda: repository.increment_flood_wait(
            session, workspace_id=workspace_id, account_id=account_id, now=now
        ),
    )


def _safe(event_name: str, fn: Callable[[], object]) -> None:
    try:
        fn()
    except Exception:
        logger.exception("Account survival hook failed: %s", event_name)
