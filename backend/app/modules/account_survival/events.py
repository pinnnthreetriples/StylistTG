from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.modules.account_survival import repository
from app.modules.account_survival.metrics import account_survival_metrics

logger = logging.getLogger(__name__)


def on_account_imported(
    session: Session, *, account_id: str, workspace_id: str, now: datetime
) -> None:
    _safe(
        "account_imported",
        lambda: _mark_account_imported(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
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
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
    preset: str | None = None,
) -> None:
    _safe(
        "warmup_completed",
        lambda: _mark_warmup_completed(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            now=now,
            preset=preset,
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
        lambda: _mark_account_terminal(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            terminal_status=terminal_status,
            now=now,
        ),
    )


def on_flood_wait(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
    action_type: str | None = None,
) -> None:
    _safe(
        "flood_wait",
        lambda: (
            repository.increment_flood_wait(
                session, workspace_id=workspace_id, account_id=account_id, now=now
            ),
            account_survival_metrics.warmup_flood_wait(
                action_type=action_type, workspace_id=workspace_id
            )
            if action_type is not None
            else None,
        ),
    )


def on_warmup_action_executed(*, action_type: str, result: str, workspace_id: str) -> None:
    _safe(
        "warmup_action_executed",
        lambda: account_survival_metrics.warmup_action_executed(
            action_type=action_type,
            result=result,
            workspace_id=workspace_id,
        ),
    )


def _mark_account_imported(
    session: Session, *, account_id: str, workspace_id: str, now: datetime
) -> None:
    is_new_metric = repository.get_metric(
        session, workspace_id=workspace_id, account_id=account_id
    ) is None
    repository.ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    if is_new_metric:
        account_survival_metrics.account_survival_observed(
            state="alive", workspace_id=workspace_id
        )


def _mark_warmup_completed(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
    preset: str | None,
) -> None:
    row = repository.get_metric(session, workspace_id=workspace_id, account_id=account_id)
    is_new_completion = row is None or row.warmup_completed_at is None
    repository.mark_warmup_completed(
        session, workspace_id=workspace_id, account_id=account_id, now=now
    )
    if is_new_completion and preset is not None:
        account_survival_metrics.warmup_session_completed(
            preset=preset, workspace_id=workspace_id
        )


def _mark_account_terminal(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    terminal_status: str,
    now: datetime,
) -> None:
    row = repository.get_metric(session, workspace_id=workspace_id, account_id=account_id)
    is_new_terminal = (
        row is None
        or (terminal_status == "banned" and row.banned_at is None)
        or (terminal_status == "deleted" and row.deleted_at is None)
    )
    repository.mark_terminal(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        terminal_status=terminal_status,
        now=now,
    )
    if is_new_terminal:
        account_survival_metrics.account_survival_observed(
            state=terminal_status, workspace_id=workspace_id
        )


def _safe(event_name: str, fn: Callable[[], object]) -> None:
    try:
        fn()
    except Exception:
        logger.exception("Account survival hook failed: %s", event_name)
