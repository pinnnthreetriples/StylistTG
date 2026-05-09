from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountSafetyOverride
from app.services.account_cooldowns import OPERATION_KEYS
from app.services.accounts import get_account
from app.services.operation_logs import log_operation

NON_OVERRIDABLE_BLOCKERS = {
    "SESSION_REVOKED",
    "AUTH_KEY_UNREGISTERED",
    "PHONE_NUMBER_BANNED",
    "missing_tdlib_credentials",
    "runtime_broken",
    "reauth_required",
}
OVERRIDE_TTL_MINUTES = 30


def create_safety_override(
    session: Session,
    account_id: str,
    *,
    workspace_id: str,
    operation: str,
    reason: str,
    requested_blockers: list[str],
) -> dict:
    if get_account(session, account_id, workspace_id=workspace_id) is None:
        raise ValueError("account not found")
    if operation not in OPERATION_KEYS:
        raise ValueError("unsupported safety operation")
    if not reason.strip():
        raise ValueError("override reason is required")
    blockers = sorted(set(requested_blockers))
    non_overridable = [code for code in blockers if code in NON_OVERRIDABLE_BLOCKERS]
    if non_overridable:
        raise ValueError(f"non-overridable blocker: {non_overridable[0]}")
    now = datetime.now(UTC)
    row = AccountSafetyOverride(
        account_id=account_id,
        operation=operation,
        reason=reason.strip(),
        requested_blockers_json=blockers,
        allowed_until=now + timedelta(minutes=OVERRIDE_TTL_MINUTES),
        created_at=now,
    )
    session.add(row)
    log_operation(
        session,
        account_id=account_id,
        operation_type="safety_override",
        operation_key=operation,
        status="completed",
        severity="warning",
        source="account_safety",
        message="Manual safety review saved",
        metadata={"requested_blockers": blockers},
    )
    session.commit()
    session.refresh(row)
    return safety_override_to_dict(row)


def active_overrides_by_operation(
    session: Session,
    account_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, list[dict]]:
    now = now or datetime.now(UTC)
    rows = session.execute(
        select(AccountSafetyOverride)
        .where(AccountSafetyOverride.account_id == account_id)
        .where(AccountSafetyOverride.allowed_until > now)
        .order_by(AccountSafetyOverride.created_at.desc())
    ).scalars().all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.operation, []).append(safety_override_to_dict(row))
    return result


def safety_override_to_dict(row: AccountSafetyOverride) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "operation": row.operation,
        "reason": row.reason,
        "requested_blockers": row.requested_blockers_json,
        "allowed_until": row.allowed_until,
        "created_at": row.created_at,
    }
