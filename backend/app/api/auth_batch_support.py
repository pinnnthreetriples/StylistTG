from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    AuthBatch,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    TERMINAL_AUTH_BATCH_ITEM_STATUSES,
    utc_now,
)
from app.schemas import (
    AuthBatchItemRead,
    AuthBatchPhoneInput,
    AuthBatchRead,
    AuthBatchSnapshotRead,
    AuthBatchValidatePhoneInput,
)
from app.services.auth_batch_dispatcher import dispatch_once
from app.services.auth_batch_state import transition_batch, transition_item
from app.services.auth_context import AuthContext
from app.services.auth_batches import PhoneInput, get_batch
from app.services.phone_hints import required_phone_hint


def phone_input(item: AuthBatchPhoneInput | AuthBatchValidatePhoneInput) -> PhoneInput:
    return PhoneInput(phone_number=item.phone_number, label=item.label)


def snapshot(batch: AuthBatch, *, include_phone_number: bool) -> AuthBatchSnapshotRead:
    return AuthBatchSnapshotRead(
        batch=batch_read(batch),
        items=[item_read(item, include_phone_number=include_phone_number) for item in batch.items],
        server_time=utc_now(),
        poll_again_in_ms=poll_interval(batch),
    )


def batch_read(batch: AuthBatch) -> AuthBatchRead:
    return AuthBatchRead(
        id=batch.id,
        label=batch.label,
        status=batch.status,
        total_count=batch.total_count,
        success_count=batch.success_count,
        failed_count=batch.failed_count,
        cancelled_count=batch.cancelled_count,
        skipped_count=batch.skipped_count,
        max_running_commands=batch.max_running_commands,
        max_waiting_input=batch.max_waiting_input,
        max_total_active=batch.max_total_active,
        created_at=batch.created_at,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
    )


def item_read(item: AuthBatchItem, *, include_phone_number: bool) -> AuthBatchItemRead:
    return AuthBatchItemRead(
        id=item.id,
        batch_id=item.batch_id,
        account_id=item.account_id,
        phone_number=item.phone_number if include_phone_number else None,
        phone_hint=required_phone_hint(item.phone_number),
        label=item.label,
        position=item.position,
        status=item.status,
        attempt_count=item.attempt_count,
        resend_count=item.resend_count,
        code_error_count=item.code_error_count,
        password_error_count=item.password_error_count,
        code_expires_at=item.code_expires_at,
        next_retry_at=item.next_retry_at,
        error_code=item.error_code,
        error_message=item.error_message,
        updated_at=item.updated_at,
        authorized_at=item.authorized_at,
    )


def can_view_full_phone(auth: AuthContext) -> bool:
    return auth.role in {"operator", "admin", "owner"}


def require_batch(session: Session, batch_id: str, workspace_id: str | None = None) -> AuthBatch:
    batch = get_batch(session, batch_id, workspace_id=workspace_id)
    if batch is None:
        raise AppError(
            status_code=404,
            error_code="AUTH_BATCH_NOT_FOUND",
            error_class="not_found",
            message="auth batch not found",
        )
    return batch


def require_item_in_batch(
    session: Session, batch_id: str, item_id: str, workspace_id: str
) -> AuthBatchItem:
    require_batch(session, batch_id, workspace_id)
    item = session.get(AuthBatchItem, item_id)
    if item is None or item.batch_id != batch_id:
        raise AppError(
            status_code=404,
            error_code="AUTH_BATCH_ITEM_NOT_FOUND",
            error_class="not_found",
            message="auth batch item not found",
        )
    return item


def poll_interval(batch: AuthBatch) -> int:
    if batch.status in {"completed", "failed", "cancelled"}:
        return 0
    if any(item.status in {"waiting_code", "waiting_2fa"} for item in batch.items):
        return 2000
    if batch.status == "paused":
        return 15000
    return 3000


def dispatch_or_raise_queue_unavailable(session: Session, batch: AuthBatch) -> None:
    launched = dispatch_once(session, batch.id)
    session.refresh(batch)
    if launched > 0 or not looks_like_queue_enqueue_failure(batch):
        return

    for item in batch.items:
        if item.status in TERMINAL_AUTH_BATCH_ITEM_STATUSES:
            continue
        item.error_code = "QUEUE_UNAVAILABLE"
        item.error_message = "job queue is unavailable"
        item.locked_by = None
        item.lock_expires_at = None
        transition_item(
            item,
            AuthBatchItemStatus.FAILED,
            actor="system",
            payload={"error_code": "QUEUE_UNAVAILABLE"},
        )
    if batch.status != AuthBatchStatus.FAILED:
        transition_batch(
            batch,
            AuthBatchStatus.FAILED,
            actor="system",
            payload={"error_code": "QUEUE_UNAVAILABLE"},
        )
    session.commit()
    raise AppError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code="QUEUE_UNAVAILABLE",
        error_class="queue",
        message="job queue is unavailable",
    )


def looks_like_queue_enqueue_failure(batch: AuthBatch) -> bool:
    active_or_waiting = {
        AuthBatchItemStatus.STARTING,
        AuthBatchItemStatus.WAITING_CODE,
        AuthBatchItemStatus.WAITING_2FA,
    }
    has_active_or_waiting = any(item.status in active_or_waiting for item in batch.items)
    has_queue_failure = any(item.error_code == "QUEUE_UNAVAILABLE" for item in batch.items)
    has_queued = any(item.status == AuthBatchItemStatus.QUEUED for item in batch.items)
    return not has_active_or_waiting and (has_queue_failure or has_queued)


def conflict(message: str) -> AppError:
    return AppError(
        status_code=409,
        error_code="AUTH_BATCH_STATE_CONFLICT",
        error_class="state",
        message=message,
    )
