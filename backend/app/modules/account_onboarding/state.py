from __future__ import annotations

from typing import Any, cast

from app.models import (
    AccountOnboardingBatch,
    AccountOnboardingEvent,
    AccountOnboardingItem,
    utc_now,
)
from app.modules.account_onboarding.errors import invalid_state

TERMINAL_ITEM_STATUSES = {
    "ready",
    "failed",
    "cancelled",
    "duplicate",
    "existing",
    "unsupported",
    "blocked",
    "requires_reauth",
}

_BATCH_TRANSITIONS = {
    "created": {"validating", "uploaded", "cancelled", "expired"},
    "uploaded": {"validating", "cancelled", "expired"},
    "validating": {"preview_ready", "failed", "cancelled", "expired"},
    "preview_ready": {"confirmed", "cancelled", "expired", "validating"},
    "confirmed": {"queued", "failed", "cancelled"},
    "queued": {"running", "failed", "cancelled"},
    "running": {"partially_completed", "completed", "failed", "cancelled"},
    "partially_completed": {"running", "completed", "failed", "cancelled"},
}

_ITEM_TRANSITIONS = {
    "pending": {"validating", "cancelled"},
    "validating": {
        "valid",
        "duplicate",
        "existing",
        "unsupported",
        "blocked",
        "requires_reauth",
        "failed",
        "cancelled",
    },
    "valid": {"queued", "requires_reauth", "cancelled"},
    "queued": {"starting_auth", "importing_session", "checking_session", "failed", "cancelled"},
    "starting_auth": {"waiting_code", "waiting_2fa", "checking_session", "ready", "failed"},
    "waiting_code": {"checking_session", "waiting_2fa", "ready", "failed", "cancelled"},
    "waiting_2fa": {"checking_session", "ready", "failed", "cancelled"},
    "importing_session": {"checking_session", "requires_reauth", "failed", "cancelled"},
    "checking_session": {"ready", "requires_reauth", "failed", "cancelled"},
    "failed": {"queued", "cancelled"},
    "requires_reauth": {"queued", "cancelled"},
}


def transition_batch(
    batch: AccountOnboardingBatch,
    new_status: str,
    *,
    actor_user_id: str | None = None,
    actor_type: str = "system",
    payload: dict[str, Any] | None = None,
) -> AccountOnboardingEvent:
    if batch.status != new_status and new_status not in _BATCH_TRANSITIONS.get(batch.status, set()):
        raise invalid_state(f"Cannot transition batch from {batch.status} to {new_status}.")
    before = batch.status
    now = utc_now()
    batch.status = new_status
    batch.updated_at = now
    if new_status == "confirmed":
        batch.confirmed_at = now
    elif new_status == "queued":
        batch.queued_at = now
    elif new_status == "running":
        batch.started_at = batch.started_at or now
    elif new_status == "completed":
        batch.completed_at = now
    elif new_status == "cancelled":
        batch.cancelled_at = now
    return event(
        batch,
        "batch.status_changed",
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        payload={"from": before, "to": new_status, **(payload or {})},
    )


def transition_item(
    item: AccountOnboardingItem,
    new_status: str,
    *,
    actor_user_id: str | None = None,
    actor_type: str = "system",
    payload: dict[str, Any] | None = None,
) -> AccountOnboardingEvent:
    if item.status != new_status and new_status not in _ITEM_TRANSITIONS.get(item.status, set()):
        raise invalid_state(f"Cannot transition item from {item.status} to {new_status}.")
    before = item.status
    now = utc_now()
    item.status = new_status
    item.updated_at = now
    if new_status == "queued":
        item.queued_at = now
    elif new_status in {"starting_auth", "importing_session", "checking_session"}:
        item.started_at = item.started_at or now
    elif new_status == "ready":
        item.ready_at = now
    elif new_status == "failed":
        item.failed_at = now
    elif new_status == "cancelled":
        item.cancelled_at = now
    if new_status == "requires_reauth":
        item.requires_reauth = True
    recalculate_batch_counters(item.batch)
    return event(
        item.batch,
        "item.status_changed",
        item=item,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        payload={"from": before, "to": new_status, **(payload or {})},
    )


def recalculate_batch_counters(batch: AccountOnboardingBatch) -> None:
    items = list(batch.items)
    batch.total_count = len(items)
    batch.valid_count = sum(1 for item in items if item.status in {"valid", "queued", "ready"})
    batch.ready_count = sum(1 for item in items if item.status == "ready")
    batch.failed_count = sum(1 for item in items if item.status == "failed")
    batch.blocked_count = sum(1 for item in items if item.status in {"blocked", "unsupported"})
    batch.requires_reauth_count = sum(
        1 for item in items if item.status == "requires_reauth" or item.requires_reauth
    )


def maybe_finish_batch(batch: AccountOnboardingBatch) -> None:
    if batch.status not in {"running", "queued", "partially_completed"}:
        return
    if any(item.status not in TERMINAL_ITEM_STATUSES for item in batch.items):
        return
    if batch.ready_count and batch.ready_count < batch.total_count:
        transition_batch(batch, "partially_completed")
    elif batch.ready_count == batch.total_count:
        transition_batch(batch, "completed")
    else:
        transition_batch(batch, "failed")


def event(
    batch: AccountOnboardingBatch,
    event_type: str,
    *,
    item: AccountOnboardingItem | None = None,
    actor_user_id: str | None = None,
    actor_type: str = "system",
    payload: dict[str, Any] | None = None,
) -> AccountOnboardingEvent:
    safe_payload = _safe_payload(payload if payload is not None else {})
    row = AccountOnboardingEvent(
        workspace_id=batch.workspace_id,
        batch_id=batch.id,
        item_id=item.id if item else None,
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        safe_payload_json=safe_payload,
    )
    batch.events.append(row)
    return row


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blocked = ("code", "password", "api_hash", "proxy_password", "object_key", "path", "session")
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if any(token in key.lower() for token in blocked):
            out[key] = "[redacted]"
        elif isinstance(value, dict):
            out[key] = _safe_payload(cast(dict[str, Any], value))
        else:
            out[key] = value
    return out
