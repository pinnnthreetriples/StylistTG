from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountQuarantine,
    QUARANTINE_REASONS,
    WorkspaceSafetyPolicy,
    new_id,
    utc_now,
)
from app.modules.account_safety.policy import get_workspace_safety_policy
from app.observability.safety_metrics import safety_metrics


class QuarantineNotFound(LookupError):
    pass


class AccountQuarantineService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def open_quarantine(
        self,
        *,
        account_id: str,
        workspace_id: str,
        reason: str,
        duration_hours: int,
        metadata: dict[str, Any] | None = None,
    ) -> AccountQuarantine:
        return create_quarantine(
            self._session,
            account_id=account_id,
            workspace_id=workspace_id,
            reason=reason,
            duration_hours=duration_hours,
            metadata=metadata,
        )

    @staticmethod
    def admin_override_release(
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        actor_user_id: str,
        reason: str,
    ) -> AccountQuarantine:
        return admin_override_release(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            actor_user_id=actor_user_id,
            reason=reason,
        )


def get_active_quarantine(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> AccountQuarantine | None:
    check_time = now or utc_now()
    return session.execute(
        select(AccountQuarantine)
        .where(AccountQuarantine.workspace_id == workspace_id)
        .where(AccountQuarantine.account_id == account_id)
        .where(AccountQuarantine.released_at.is_(None))
        .where(AccountQuarantine.until > check_time)
        .order_by(AccountQuarantine.until.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_unreleased_quarantine(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> AccountQuarantine | None:
    return session.execute(
        select(AccountQuarantine)
        .where(AccountQuarantine.workspace_id == workspace_id)
        .where(AccountQuarantine.account_id == account_id)
        .where(AccountQuarantine.released_at.is_(None))
        .order_by(AccountQuarantine.until.desc())
        .limit(1)
    ).scalar_one_or_none()


def create_quarantine(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    reason: str,
    duration_hours: int,
    metadata: dict[str, Any] | None = None,
) -> AccountQuarantine:
    if reason not in QUARANTINE_REASONS:
        raise ValueError(f"quarantine reason is not supported: {reason}")
    if duration_hours <= 0:
        raise ValueError("duration_hours must be positive")

    now = utc_now()
    until = now + timedelta(hours=duration_hours)
    existing = get_unreleased_quarantine(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    if existing is not None:
        existing.until = max(existing.until, until)
        if metadata:
            existing.metadata_json = {**dict(existing.metadata_json or {}), **metadata}
        session.flush()
        _refresh_quarantine_active(session, workspace_id=workspace_id, reason=existing.reason)
        return existing

    row = AccountQuarantine(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        reason=reason,
        started_at=now,
        until=until,
        metadata_json=metadata or {},
    )
    session.add(row)
    session.flush()
    safety_metrics.quarantine_opened(workspace_id=workspace_id, reason=reason)
    _refresh_quarantine_active(session, workspace_id=workspace_id, reason=reason)
    return row


def release_quarantine(
    session: Session,
    *,
    quarantine_id: str,
    workspace_id: str,
    released_by: str,
    reason: str | None = None,
) -> AccountQuarantine:
    row = session.execute(
        select(AccountQuarantine)
        .where(AccountQuarantine.id == quarantine_id)
        .where(AccountQuarantine.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if row is None:
        raise QuarantineNotFound(quarantine_id)

    row.released_at = utc_now()
    row.released_by_user_id = released_by
    metadata = dict(row.metadata_json or {})
    if reason:
        metadata["release_reason"] = reason
    row.metadata_json = metadata
    session.flush()
    safety_metrics.quarantine_released(
        workspace_id=workspace_id,
        reason=row.reason,
        mode="manual",
    )
    _refresh_quarantine_active(session, workspace_id=workspace_id, reason=row.reason)
    return row


def admin_override_release(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    actor_user_id: str,
    reason: str,
) -> AccountQuarantine:
    if len(reason.strip()) < 10:
        raise ValueError("reason must be at least 10 characters")

    row = get_active_quarantine(session, account_id=account_id, workspace_id=workspace_id)
    if row is None:
        raise QuarantineNotFound(account_id)

    now = utc_now()
    row.released_at = now
    row.released_by_user_id = actor_user_id
    metadata = dict(row.metadata_json or {})
    metadata["admin_override_release_reason"] = reason.strip()
    metadata["admin_override_released_at"] = now.isoformat()
    row.metadata_json = metadata
    session.flush()
    safety_metrics.quarantine_released(
        workspace_id=workspace_id,
        reason=row.reason,
        mode="admin_override",
    )
    _refresh_quarantine_active(session, workspace_id=workspace_id, reason=row.reason)
    return row


def is_account_quarantined(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> bool:
    return (
        get_active_quarantine(session, account_id=account_id, workspace_id=workspace_id) is not None
    )


def handle_flood_wait(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    flood_wait_seconds: int,
    source_attempt_id: str | None,
) -> AccountQuarantine:
    policy: WorkspaceSafetyPolicy | None = get_workspace_safety_policy(
        session,
        workspace_id=workspace_id,
        create_if_missing=False,
    )
    quarantine_hours = policy.quarantine_hours_on_flood_wait if policy is not None else 24
    return create_quarantine(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
        reason="flood_wait",
        duration_hours=quarantine_hours,
        metadata={
            "original_flood_wait_seconds": flood_wait_seconds,
            "source_attempt_id": source_attempt_id,
        },
    )


def _refresh_quarantine_active(session: Session, *, workspace_id: str, reason: str) -> None:
    active_count = int(
        session.scalar(
            select(func.count(AccountQuarantine.id))
            .where(AccountQuarantine.workspace_id == workspace_id)
            .where(AccountQuarantine.reason == reason)
            .where(AccountQuarantine.released_at.is_(None))
            .where(AccountQuarantine.until > utc_now())
        )
        or 0
    )
    account_count = int(
        session.scalar(select(func.count(Account.id)).where(Account.workspace_id == workspace_id))
        or 0
    )
    safety_metrics.account_total(workspace_id=workspace_id, value=account_count)
    safety_metrics.quarantine_active(
        workspace_id=workspace_id,
        reason=reason,
        value=active_count,
    )


__all__ = [
    "AccountQuarantineService",
    "QuarantineNotFound",
    "admin_override_release",
    "create_quarantine",
    "get_active_quarantine",
    "get_unreleased_quarantine",
    "handle_flood_wait",
    "is_account_quarantined",
    "release_quarantine",
]
