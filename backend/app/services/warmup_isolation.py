"""Warmup isolation claim service.

Единая поверхность, через которую будущие модули (Кампании, Рассылки,
Парсинг) проверяют, можно ли производить с аккаунтом live-действия.
Пока аккаунт находится в активной сессии прогрева, сторонние модули
получают `AppError(409)` с error_code=`ACCOUNT_ISOLATED_BY_WARMUP`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import WarmupIsolationClaim, utc_now


ISOLATION_ERROR_CODE = "ACCOUNT_ISOLATED_BY_WARMUP"


@dataclass(frozen=True)
class IsolationClaimSnapshot:
    account_id: str
    workspace_id: str
    held_by: str
    reason: str
    acquired_at: datetime


def get_claim(session: Session, *, account_id: str) -> IsolationClaimSnapshot | None:
    row = session.get(WarmupIsolationClaim, account_id)
    if row is None:
        return None
    return IsolationClaimSnapshot(
        account_id=row.account_id,
        workspace_id=row.workspace_id,
        held_by=row.held_by,
        reason=row.reason,
        acquired_at=row.acquired_at,
    )


def acquire_claim(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    held_by: str,
    reason: str,
    now: datetime | None = None,
) -> bool:
    """Create an isolation claim for an account.

    Returns True if the claim was newly created or already held by the same
    owner (idempotent). Returns False if another owner already holds the claim.
    """
    timestamp = now or utc_now()
    existing = session.get(WarmupIsolationClaim, account_id)
    if existing is not None:
        return existing.held_by == held_by
    nested = session.begin_nested()
    try:
        session.add(
            WarmupIsolationClaim(
                account_id=account_id,
                workspace_id=workspace_id,
                held_by=held_by,
                reason=reason,
                acquired_at=timestamp,
            )
        )
        session.flush()
        return True
    except IntegrityError:
        nested.rollback()
        session.expire_all()
        reloaded = session.get(WarmupIsolationClaim, account_id)
        if reloaded is not None:
            return reloaded.held_by == held_by
        return False


def release_claim(
    session: Session,
    *,
    account_id: str,
    held_by: str,
) -> bool:
    """Release an isolation claim held by `held_by`.

    Returns True on successful release, False if no claim exists or if the
    claim is held by a different owner (defensive: never release foreign claims).
    """
    existing = session.get(WarmupIsolationClaim, account_id)
    if existing is None:
        return False
    if existing.held_by != held_by:
        return False
    session.delete(existing)
    session.flush()
    return True


def ensure_not_isolated(session: Session, *, account_id: str) -> None:
    """Raise AppError(409) if account is currently isolated by a warmup session.

    Intended for use in Campaigns / Broadcasts / Parsing modules as a guard.
    """
    claim = get_claim(session, account_id=account_id)
    if claim is None:
        return
    raise AppError(
        status_code=409,
        error_code=ISOLATION_ERROR_CODE,
        error_class="state_conflict",
        message="account is currently isolated by an active warmup session",
        details={
            "account_id": claim.account_id,
            "held_by": claim.held_by,
            "reason": claim.reason,
            "acquired_at": claim.acquired_at.isoformat(),
        },
    )


def list_claims_for_workspace(
    session: Session, *, workspace_id: str
) -> list[IsolationClaimSnapshot]:
    rows = session.execute(
        select(WarmupIsolationClaim).where(
            WarmupIsolationClaim.workspace_id == workspace_id
        )
    ).scalars().all()
    return [
        IsolationClaimSnapshot(
            account_id=row.account_id,
            workspace_id=row.workspace_id,
            held_by=row.held_by,
            reason=row.reason,
            acquired_at=row.acquired_at,
        )
        for row in rows
    ]
