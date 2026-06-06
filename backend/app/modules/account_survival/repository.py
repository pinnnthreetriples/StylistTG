from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountSurvivalMetric, new_id


def get_metric(
    session: Session, *, workspace_id: str, account_id: str
) -> AccountSurvivalMetric | None:
    return session.execute(
        select(AccountSurvivalMetric).where(
            AccountSurvivalMetric.workspace_id == workspace_id,
            AccountSurvivalMetric.account_id == account_id,
        )
    ).scalar_one_or_none()


def ensure_metric(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    imported_at: datetime,
    now: datetime,
) -> AccountSurvivalMetric:
    row = get_metric(session, workspace_id=workspace_id, account_id=account_id)
    if row is not None:
        return row
    row = AccountSurvivalMetric(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=imported_at,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    return row


def list_metrics(session: Session, *, workspace_id: str) -> list[AccountSurvivalMetric]:
    return list(
        session.execute(
            select(AccountSurvivalMetric)
            .where(AccountSurvivalMetric.workspace_id == workspace_id)
            .order_by(AccountSurvivalMetric.imported_at.asc())
        ).scalars()
    )


def mark_warmup_started(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    now: datetime,
    strategy_id: str | None,
    strategy_name: str | None,
) -> AccountSurvivalMetric:
    row = ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    if row.warmup_started_at is None:
        row.warmup_started_at = now
    if row.warmup_strategy_id is None:
        row.warmup_strategy_id = strategy_id
    if row.warmup_strategy_name is None:
        row.warmup_strategy_name = strategy_name
    row.updated_at = now
    return row


def mark_warmup_completed(
    session: Session, *, workspace_id: str, account_id: str, now: datetime
) -> AccountSurvivalMetric:
    row = ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    if row.warmup_completed_at is None:
        row.warmup_completed_at = now
    row.updated_at = now
    return row


def mark_freeze(
    session: Session, *, workspace_id: str, account_id: str, now: datetime
) -> AccountSurvivalMetric:
    row = ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    if row.first_freeze_at is None:
        row.first_freeze_at = now
    row.freeze_count += 1
    row.updated_at = now
    return row


def mark_terminal(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    terminal_status: str,
    now: datetime,
) -> AccountSurvivalMetric:
    row = ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    if terminal_status == "banned" and row.banned_at is None:
        row.banned_at = now
    if terminal_status == "deleted" and row.deleted_at is None:
        row.deleted_at = now
    row.updated_at = now
    return row


def increment_flood_wait(
    session: Session, *, workspace_id: str, account_id: str, now: datetime
) -> AccountSurvivalMetric:
    row = ensure_metric(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        imported_at=now,
        now=now,
    )
    row.flood_wait_count += 1
    row.updated_at = now
    return row
