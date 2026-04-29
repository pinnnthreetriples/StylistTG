from __future__ import annotations

from app.models import (
    AuthBatch,
    AuthBatchEvent,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    TERMINAL_AUTH_BATCH_ITEM_STATUSES,
    utc_now,
)


class InvalidAuthBatchTransition(ValueError):
    pass


ITEM_TRANSITIONS: dict[str, set[str]] = {
    AuthBatchItemStatus.QUEUED: {
        AuthBatchItemStatus.STARTING,
        AuthBatchItemStatus.FAILED,
        AuthBatchItemStatus.SKIPPED,
        AuthBatchItemStatus.CANCELLED,
    },
    AuthBatchItemStatus.STARTING: {
        AuthBatchItemStatus.WAITING_CODE,
        AuthBatchItemStatus.WAITING_2FA,
        AuthBatchItemStatus.AUTHORIZED,
        AuthBatchItemStatus.QUEUED,
        AuthBatchItemStatus.FAILED,
        AuthBatchItemStatus.CANCELLED,
        AuthBatchItemStatus.TIMED_OUT,
    },
    AuthBatchItemStatus.WAITING_CODE: {
        AuthBatchItemStatus.WAITING_2FA,
        AuthBatchItemStatus.AUTHORIZED,
        AuthBatchItemStatus.FAILED,
        AuthBatchItemStatus.CANCELLED,
        AuthBatchItemStatus.TIMED_OUT,
        AuthBatchItemStatus.STARTING,
    },
    AuthBatchItemStatus.WAITING_2FA: {
        AuthBatchItemStatus.AUTHORIZED,
        AuthBatchItemStatus.FAILED,
        AuthBatchItemStatus.CANCELLED,
        AuthBatchItemStatus.TIMED_OUT,
    },
    AuthBatchItemStatus.FAILED: {AuthBatchItemStatus.QUEUED},
    AuthBatchItemStatus.TIMED_OUT: {AuthBatchItemStatus.QUEUED, AuthBatchItemStatus.STARTING},
    AuthBatchItemStatus.AUTHORIZED: set(),
    AuthBatchItemStatus.CANCELLED: set(),
    AuthBatchItemStatus.SKIPPED: set(),
}

BATCH_TRANSITIONS: dict[str, set[str]] = {
    AuthBatchStatus.PENDING: {AuthBatchStatus.RUNNING, AuthBatchStatus.CANCELLED},
    AuthBatchStatus.RUNNING: {
        AuthBatchStatus.PAUSED,
        AuthBatchStatus.COMPLETED,
        AuthBatchStatus.FAILED,
        AuthBatchStatus.CANCELLED,
    },
    AuthBatchStatus.PAUSED: {AuthBatchStatus.RUNNING, AuthBatchStatus.CANCELLED},
    AuthBatchStatus.COMPLETED: set(),
    AuthBatchStatus.FAILED: set(),
    AuthBatchStatus.CANCELLED: set(),
}


def transition_batch(
    batch: AuthBatch,
    new_status: str,
    *,
    actor: str = "system",
    payload: dict | None = None,
) -> None:
    if new_status == batch.status:
        return
    if new_status not in BATCH_TRANSITIONS.get(str(batch.status), set()):
        raise InvalidAuthBatchTransition(f"cannot transition batch {batch.status} to {new_status}")
    old_status = batch.status
    batch.status = new_status
    batch.version += 1
    now = utc_now()
    if new_status == AuthBatchStatus.RUNNING and batch.started_at is None:
        batch.started_at = now
    if new_status in {AuthBatchStatus.COMPLETED, AuthBatchStatus.FAILED, AuthBatchStatus.CANCELLED}:
        batch.finished_at = now
    batch.events.append(
        AuthBatchEvent(
            event_type="batch_status_changed",
            actor=actor,
            payload_json={"from": str(old_status), "to": str(new_status), **(payload or {})},
        )
    )


def transition_item(
    item: AuthBatchItem,
    new_status: str,
    *,
    actor: str = "system",
    payload: dict | None = None,
) -> None:
    if new_status == item.status:
        return
    if new_status not in ITEM_TRANSITIONS.get(str(item.status), set()):
        raise InvalidAuthBatchTransition(f"cannot transition item {item.status} to {new_status}")
    old_status = item.status
    was_terminal = old_status in TERMINAL_AUTH_BATCH_ITEM_STATUSES
    item.status = new_status
    item.updated_at = utc_now()
    if new_status == AuthBatchItemStatus.AUTHORIZED:
        item.authorized_at = utc_now()
    if was_terminal and new_status not in TERMINAL_AUTH_BATCH_ITEM_STATUSES:
        _decrement_batch_counter(item.batch, old_status)
    if not was_terminal and new_status in TERMINAL_AUTH_BATCH_ITEM_STATUSES:
        _increment_batch_counter(item.batch, new_status)
    item.events.append(
        AuthBatchEvent(
            batch_id=item.batch_id,
            event_type="item_status_changed",
            actor=actor,
            payload_json={"from": str(old_status), "to": str(new_status), **(payload or {})},
        )
    )
    _finish_batch_if_complete(item.batch)


def _increment_batch_counter(batch: AuthBatch, status: str) -> None:
    if status == AuthBatchItemStatus.AUTHORIZED:
        batch.success_count += 1
    elif status == AuthBatchItemStatus.FAILED:
        batch.failed_count += 1
    elif status == AuthBatchItemStatus.CANCELLED:
        batch.cancelled_count += 1
    elif status == AuthBatchItemStatus.SKIPPED:
        batch.skipped_count += 1
    elif status == AuthBatchItemStatus.TIMED_OUT:
        batch.failed_count += 1


def _decrement_batch_counter(batch: AuthBatch, status: str) -> None:
    if status == AuthBatchItemStatus.AUTHORIZED:
        batch.success_count = max(0, batch.success_count - 1)
    elif status == AuthBatchItemStatus.FAILED:
        batch.failed_count = max(0, batch.failed_count - 1)
    elif status == AuthBatchItemStatus.CANCELLED:
        batch.cancelled_count = max(0, batch.cancelled_count - 1)
    elif status == AuthBatchItemStatus.SKIPPED:
        batch.skipped_count = max(0, batch.skipped_count - 1)
    elif status == AuthBatchItemStatus.TIMED_OUT:
        batch.failed_count = max(0, batch.failed_count - 1)


def _finish_batch_if_complete(batch: AuthBatch) -> None:
    terminal_count = (
        batch.success_count
        + batch.failed_count
        + batch.cancelled_count
        + batch.skipped_count
    )
    if batch.total_count <= 0 or terminal_count < batch.total_count:
        return
    if batch.status not in {AuthBatchStatus.RUNNING, AuthBatchStatus.PAUSED, AuthBatchStatus.PENDING}:
        return
    if batch.success_count > 0:
        batch.status = AuthBatchStatus.COMPLETED
    else:
        batch.status = AuthBatchStatus.FAILED
    batch.finished_at = utc_now()
