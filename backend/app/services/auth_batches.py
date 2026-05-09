from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import normalize_phone_number
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountRuntimeState,
    AccountState,
    AuthBatch,
    AuthBatchEvent,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    TERMINAL_AUTH_BATCH_STATUSES,
    IdempotencyKey,
    TERMINAL_AUTH_BATCH_ITEM_STATUSES,
    utc_now,
)
from app.services.accounts import get_account_by_external_ref
from app.services.audit_logs import log_audit_event
from app.services.auth_batch_state import transition_batch, transition_item
from app.services.limits import check_workspace_limit
from app.services.workspaces import ensure_default_workspace

REUSABLE_BATCH_ACCOUNT_STATES = {
    AccountState.REGISTERED,
    AccountState.AUTH_PENDING,
    AccountState.AWAITING_CODE,
    AccountState.AWAITING_PASSWORD,
}


@dataclass(frozen=True)
class PhoneInput:
    phone_number: str
    label: str | None = None


class EmptyAuthBatchError(ValueError):
    def __init__(self, validation: dict) -> None:
        super().__init__("No new Telegram accounts to add. Check existing accounts, duplicates, and invalid numbers.")
        self.validation = validation


def validate_batch_phones(
    session: Session,
    inputs: list[PhoneInput],
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> dict:
    valid_items: list[dict] = []
    invalid_items: list[dict] = []
    duplicates: list[dict] = []
    existing_accounts: list[dict] = []
    active_batch_conflicts: list[dict] = []
    seen: set[str] = set()

    for position, item in enumerate(inputs):
        raw = item.phone_number
        try:
            normalized = normalize_phone_number(raw)
        except ValueError as exc:
            invalid_items.append(
                {"input": raw, "label": item.label, "position": position, "error": str(exc)}
            )
            continue

        row = {"phone_number": normalized, "label": item.label, "position": position}
        if normalized in seen:
            duplicates.append({**row, "account_id": None, "batch_item_id": None})
            continue
        seen.add(normalized)

        active_item = session.execute(
            select(AuthBatchItem)
            .join(AuthBatch, AuthBatch.id == AuthBatchItem.batch_id)
            .where(AuthBatch.workspace_id == workspace_id)
            .where(AuthBatchItem.phone_number == normalized)
            .where(AuthBatchItem.status.not_in([state.value for state in TERMINAL_AUTH_BATCH_ITEM_STATUSES]))
        ).scalars().first()
        if active_item is not None:
            active_batch_conflicts.append(
                {
                    **row,
                    "account_id": active_item.account_id,
                    "batch_item_id": active_item.id,
                    "batch_id": active_item.batch_id,
                }
            )
            continue

        account = get_account_by_external_ref(session, normalized, workspace_id=workspace_id)
        if account is not None and not _can_reuse_stale_batch_account(session, account):
            existing_accounts.append({**row, "account_id": account.id, "batch_item_id": None, "batch_id": None})
            continue

        valid_items.append(row)

    return {
        "valid_items": valid_items,
        "invalid_items": invalid_items,
        "duplicates": duplicates,
        "existing_accounts": existing_accounts,
        "active_batch_conflicts": active_batch_conflicts,
    }


def create_auth_batch(
    session: Session,
    *,
    idempotency_key: str,
    label: str | None,
    inputs: list[PhoneInput],
    max_running_commands: int = 2,
    max_waiting_input: int = 5,
    max_total_active: int = 6,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
) -> tuple[AuthBatch, bool]:
    if workspace_id == DEFAULT_LOCAL_WORKSPACE_ID:
        ensure_default_workspace(session)
    existing = session.execute(
        select(AuthBatch).where(AuthBatch.idempotency_key == idempotency_key)
    ).scalars().first()
    if existing is not None:
        return existing, False

    validation = validate_batch_phones(session, inputs, workspace_id=workspace_id)
    valid_items = validation["valid_items"]
    if not valid_items:
        raise EmptyAuthBatchError(validation)
    check_workspace_limit(session, workspace_id, "batch_size", requested=len(valid_items))

    batch = AuthBatch(
        workspace_id=workspace_id,
        label=label,
        idempotency_key=idempotency_key,
        total_count=len(valid_items),
        max_running_commands=max(1, min(max_running_commands, 5)),
        max_waiting_input=max(1, min(max_waiting_input, 10)),
        max_total_active=max(1, min(max_total_active, 12)),
    )
    session.add(batch)
    session.flush()

    for item in valid_items:
        account = get_account_by_external_ref(session, item["phone_number"], workspace_id=workspace_id)
        if account is not None and _can_reuse_stale_batch_account(session, account):
            _reset_stale_batch_account(account)
        else:
            account = Account(
                workspace_id=workspace_id,
                external_ref=item["phone_number"],
                auth_source="batch",
                account_state=AccountState.REGISTERED,
            )
            account.runtime_state = AccountRuntimeState(
                session_present=False,
                runtime_health="unknown",
                reauth_required=False,
            )
            session.add(account)
            session.flush()
        session.add(
            AuthBatchItem(
                batch_id=batch.id,
                account_id=account.id,
                phone_number=item["phone_number"],
                label=item["label"],
                position=item["position"],
                status=AuthBatchItemStatus.QUEUED,
            )
        )
    batch.events.append(
        AuthBatchEvent(event_type="batch_created", actor="user", payload_json={"total_count": len(valid_items)})
    )
    log_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="auth.batch.created",
        entity_type="auth_batch",
        entity_id=batch.id,
        metadata={"total_count": len(valid_items)},
    )
    session.commit()
    session.refresh(batch)
    return batch, True


def _can_reuse_stale_batch_account(session: Session, account: Account) -> bool:
    if account.auth_source != "batch":
        return False
    if account.account_state not in REUSABLE_BATCH_ACCOUNT_STATES:
        return False
    active_item = session.execute(
        select(AuthBatchItem.id)
        .where(AuthBatchItem.account_id == account.id)
        .where(AuthBatchItem.status.not_in([state.value for state in TERMINAL_AUTH_BATCH_ITEM_STATUSES]))
        .limit(1)
    ).scalars().first()
    return active_item is None


def _reset_stale_batch_account(account: Account) -> None:
    account.auth_source = "batch"
    account.telegram_user_id = None
    account.account_state = AccountState.REGISTERED
    account.runtime_state.session_present = False
    account.runtime_state.authorized_last_confirmed_at = None
    account.runtime_state.runtime_health = "unknown"
    account.runtime_state.reauth_required = False
    account.runtime_state.lock_owner = None
    account.runtime_state.lock_epoch = 0
    account.runtime_state.recovery_marker = None
    account.runtime_state.updated_at = utc_now()


def get_batch(session: Session, batch_id: str, workspace_id: str | None = None) -> AuthBatch | None:
    batch = session.get(AuthBatch, batch_id)
    if batch is None or (workspace_id is not None and batch.workspace_id != workspace_id):
        return None
    return batch


def list_batches(session: Session, *, limit: int = 50, workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> list[AuthBatch]:
    return list(
        session.execute(
            select(AuthBatch)
            .where(AuthBatch.workspace_id == workspace_id)
            .order_by(AuthBatch.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def start_batch(session: Session, batch_id: str, *, workspace_id: str | None = None) -> AuthBatch:
    batch = _require_batch(session, batch_id, workspace_id=workspace_id)
    transition_batch(batch, AuthBatchStatus.RUNNING, actor="user")
    session.commit()
    session.refresh(batch)
    return batch


def pause_batch(session: Session, batch_id: str, *, workspace_id: str | None = None) -> AuthBatch:
    batch = _require_batch(session, batch_id, workspace_id=workspace_id)
    transition_batch(batch, AuthBatchStatus.PAUSED, actor="user")
    session.commit()
    session.refresh(batch)
    return batch


def resume_batch(session: Session, batch_id: str, *, workspace_id: str | None = None) -> AuthBatch:
    batch = _require_batch(session, batch_id, workspace_id=workspace_id)
    transition_batch(batch, AuthBatchStatus.RUNNING, actor="user")
    session.commit()
    session.refresh(batch)
    return batch


def cancel_batch(session: Session, batch_id: str, *, workspace_id: str | None = None) -> AuthBatch:
    batch = _require_batch(session, batch_id, workspace_id=workspace_id)
    for item in batch.items:
        if item.status not in TERMINAL_AUTH_BATCH_ITEM_STATUSES:
            transition_item(item, AuthBatchItemStatus.CANCELLED, actor="user")
    if batch.status != AuthBatchStatus.CANCELLED:
        transition_batch(batch, AuthBatchStatus.CANCELLED, actor="user")
    session.commit()
    session.refresh(batch)
    return batch


def cancel_item(session: Session, item_id: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    transition_item(item, AuthBatchItemStatus.CANCELLED, actor="user")
    session.commit()
    session.refresh(item)
    return item


def retry_item(session: Session, item_id: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    if item.batch.status in TERMINAL_AUTH_BATCH_STATUSES:
        raise ValueError("terminal batch item cannot be retried")
    item.error_code = None
    item.error_message = None
    item.next_retry_at = None
    transition_item(item, AuthBatchItemStatus.QUEUED, actor="user")
    session.commit()
    session.refresh(item)
    return item


def expire_idempotency_keys(session: Session) -> int:
    now = utc_now()
    keys = list(session.execute(select(IdempotencyKey).where(IdempotencyKey.expires_at < now)).scalars())
    for key in keys:
        session.delete(key)
    session.commit()
    return len(keys)


def save_idempotency_result(
    session: Session,
    *,
    key: str,
    operation: str,
    entity_id: str,
    response_json: dict,
    ttl_seconds: int = 600,
) -> None:
    session.add(
        IdempotencyKey(
            key=key,
            operation=operation,
            entity_id=entity_id,
            response_json=response_json,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
    )


def get_idempotency_result(session: Session, *, key: str, operation: str) -> dict | None:
    row = session.get(IdempotencyKey, key)
    if row is None or row.operation != operation or row.expires_at < utc_now():
        return None
    return row.response_json


def _require_batch(session: Session, batch_id: str, *, workspace_id: str | None = None) -> AuthBatch:
    batch = get_batch(session, batch_id, workspace_id=workspace_id)
    if batch is None:
        raise ValueError("batch not found")
    return batch


def _require_item(session: Session, item_id: str) -> AuthBatchItem:
    item = session.get(AuthBatchItem, item_id)
    if item is None:
        raise ValueError("batch item not found")
    return item
