from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountQuarantine, QUARANTINE_REASONS, WorkspaceSafetyPolicy, new_id, utc_now
from app.services.workspace_safety_policy import get_workspace_safety_policy


class QuarantineNotFound(LookupError):
    pass


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
    row = AccountQuarantine(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        reason=reason,
        started_at=now,
        until=now + timedelta(hours=duration_hours),
        metadata_json=metadata or {},
    )
    session.add(row)
    session.flush()
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
