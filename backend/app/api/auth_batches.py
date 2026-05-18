from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.models import (
    AuthBatch,
    AuthBatchEvent,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    TERMINAL_AUTH_BATCH_ITEM_STATUSES,
    utc_now,
)
from app.schemas import (
    AuthBatchCreate,
    AuthBatchEventRead,
    AuthBatchItemRead,
    AuthBatchPhoneInput,
    AuthBatchPollRead,
    AuthBatchRead,
    AuthBatchSnapshotRead,
    AuthBatchSubmitCodeRequest,
    AuthBatchSubmitPasswordRequest,
    AuthBatchValidateRead,
    AuthBatchValidateRequest,
    AuthBatchValidatePhoneInput,
)
from app.services.auth_batch_dispatcher import dispatch_once
from app.services.auth_batch_state import (
    InvalidAuthBatchTransition,
    transition_batch,
    transition_item,
)
from app.services.auth_batch_tdlib import request_new_code, submit_batch_code, submit_batch_password
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.auth_batches import (
    EmptyAuthBatchError,
    PhoneInput,
    cancel_batch,
    cancel_item,
    create_auth_batch,
    get_batch,
    get_idempotency_result,
    list_batches,
    pause_batch,
    resume_batch,
    retry_item,
    save_idempotency_result,
    start_batch,
    validate_batch_phones,
)
from app.services.phone_hints import required_phone_hint

router = APIRouter(prefix="/api/auth-batches", tags=["auth-batches"])


@router.post("/validate-phones", response_model=AuthBatchValidateRead)
def validate_phones(
    payload: AuthBatchValidateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return validate_batch_phones(
        session, [_phone_input(item) for item in payload.items], workspace_id=auth.workspace_id
    )


@router.post(
    "",
    response_model=AuthBatchSnapshotRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": AuthBatchSnapshotRead}},
)
def create_batch(
    payload: AuthBatchCreate,
    response: Response,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        batch, created = create_auth_batch(
            session,
            idempotency_key=payload.idempotency_key,
            label=payload.label,
            inputs=[_phone_input(item) for item in payload.items],
            max_running_commands=payload.max_running_commands,
            max_waiting_input=payload.max_waiting_input,
            max_total_active=payload.max_total_active,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except EmptyAuthBatchError as exc:
        raise AppError(
            status_code=400,
            error_code="AUTH_BATCH_EMPTY",
            error_class="validation",
            message=str(exc),
            details=exc.validation,
        ) from exc
    except ValueError as exc:
        raise _conflict(str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return _snapshot(batch, include_phone_number=True)


@router.get("", response_model=list[AuthBatchRead])
def get_batches(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return [
        _batch_read(batch)
        for batch in list_batches(session, limit=limit, workspace_id=auth.workspace_id)
    ]


@router.get("/{batch_id}", response_model=AuthBatchSnapshotRead)
def get_batch_snapshot(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return _snapshot(
        _require_batch(session, batch_id, auth.workspace_id),
        include_phone_number=_can_view_full_phone(auth),
    )


@router.get("/{batch_id}/poll", response_model=AuthBatchPollRead)
def poll_batch(
    batch_id: str,
    updated_since: datetime | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    batch = _require_batch(session, batch_id, auth.workspace_id)
    query = select(AuthBatchItem).where(AuthBatchItem.batch_id == batch_id)
    if updated_since is not None:
        query = query.where(AuthBatchItem.updated_at > updated_since)
    items = list(session.execute(query.order_by(AuthBatchItem.position)).scalars())
    return AuthBatchPollRead(
        batch=_batch_read(batch),
        items=[_item_read(item, include_phone_number=_can_view_full_phone(auth)) for item in items],
        server_time=utc_now(),
        poll_again_in_ms=_poll_interval(batch),
    )


@router.post("/{batch_id}/start", response_model=AuthBatchSnapshotRead)
def post_start_batch(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        _require_batch(session, batch_id, auth.workspace_id)
        batch = start_batch(session, batch_id, workspace_id=auth.workspace_id)
        _dispatch_or_raise_queue_unavailable(session, batch)
        return _snapshot(batch, include_phone_number=True)
    except InvalidAuthBatchTransition as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/pause", response_model=AuthBatchSnapshotRead)
def post_pause_batch(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        _require_batch(session, batch_id, auth.workspace_id)
        return _snapshot(
            pause_batch(session, batch_id, workspace_id=auth.workspace_id),
            include_phone_number=True,
        )
    except InvalidAuthBatchTransition as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/resume", response_model=AuthBatchSnapshotRead)
def post_resume_batch(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        _require_batch(session, batch_id, auth.workspace_id)
        batch = resume_batch(session, batch_id, workspace_id=auth.workspace_id)
        _dispatch_or_raise_queue_unavailable(session, batch)
        return _snapshot(batch, include_phone_number=True)
    except InvalidAuthBatchTransition as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/cancel", response_model=AuthBatchSnapshotRead)
def post_cancel_batch(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        _require_batch(session, batch_id, auth.workspace_id)
        return _snapshot(
            cancel_batch(session, batch_id, workspace_id=auth.workspace_id),
            include_phone_number=True,
        )
    except InvalidAuthBatchTransition as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/items/{item_id}/submit-code", response_model=AuthBatchItemRead)
def post_submit_code(
    batch_id: str,
    item_id: str,
    payload: AuthBatchSubmitCodeRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    _require_item_in_batch(session, batch_id, item_id, auth.workspace_id)
    try:
        existing = get_idempotency_result(
            session,
            key=payload.idempotency_key,
            operation="submit_code",
            entity_id=item_id,
            workspace_id=auth.workspace_id,
        )
        if existing is not None:
            return existing
        item = submit_batch_code(session, item_id, payload.code)
        if item.batch.status == "running":
            dispatch_once(session, item.batch_id)
        response = _item_read(item, include_phone_number=True)
        save_idempotency_result(
            session,
            key=payload.idempotency_key,
            operation="submit_code",
            entity_id=item.id,
            response_json=response.model_dump(mode="json"),
            workspace_id=auth.workspace_id,
        )
        session.commit()
        return response
    except ValueError as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/items/{item_id}/submit-2fa", response_model=AuthBatchItemRead)
def post_submit_2fa(
    batch_id: str,
    item_id: str,
    payload: AuthBatchSubmitPasswordRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    _require_item_in_batch(session, batch_id, item_id, auth.workspace_id)
    try:
        existing = get_idempotency_result(
            session,
            key=payload.idempotency_key,
            operation="submit_2fa",
            entity_id=item_id,
            workspace_id=auth.workspace_id,
        )
        if existing is not None:
            return existing
        item = submit_batch_password(session, item_id, payload.password)
        if item.batch.status == "running":
            dispatch_once(session, item.batch_id)
        response = _item_read(item, include_phone_number=True)
        save_idempotency_result(
            session,
            key=payload.idempotency_key,
            operation="submit_2fa",
            entity_id=item.id,
            response_json=response.model_dump(mode="json"),
            workspace_id=auth.workspace_id,
        )
        session.commit()
        return response
    except ValueError as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/items/{item_id}/retry", response_model=AuthBatchItemRead)
def post_retry_item(
    batch_id: str,
    item_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    _require_item_in_batch(session, batch_id, item_id, auth.workspace_id)
    try:
        item = retry_item(session, item_id)
        if item.batch.status == "running":
            dispatch_once(session, item.batch_id)
        return _item_read(item, include_phone_number=True)
    except ValueError as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/items/{item_id}/request-new-code", response_model=AuthBatchItemRead)
def post_request_new_code(
    batch_id: str,
    item_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    _require_item_in_batch(session, batch_id, item_id, auth.workspace_id)
    try:
        item = request_new_code(session, item_id)
        if item.batch.status == "running":
            dispatch_once(session, item.batch_id)
        return _item_read(item, include_phone_number=True)
    except ValueError as exc:
        raise _conflict(str(exc)) from exc


@router.post("/{batch_id}/items/{item_id}/cancel", response_model=AuthBatchItemRead)
def post_cancel_item(
    batch_id: str,
    item_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    _require_item_in_batch(session, batch_id, item_id, auth.workspace_id)
    try:
        return _item_read(cancel_item(session, item_id), include_phone_number=True)
    except ValueError as exc:
        raise _conflict(str(exc)) from exc


@router.get("/{batch_id}/events", response_model=list[AuthBatchEventRead])
def get_batch_events(
    batch_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    _require_batch(session, batch_id, auth.workspace_id)
    events = session.execute(
        select(AuthBatchEvent)
        .where(AuthBatchEvent.batch_id == batch_id)
        .order_by(AuthBatchEvent.created_at)
    ).scalars()
    return [
        AuthBatchEventRead(
            id=event.id,
            batch_id=event.batch_id,
            batch_item_id=event.batch_item_id,
            event_type=event.event_type,
            actor=event.actor,
            payload_json=event.payload_json,
            created_at=event.created_at,
        )
        for event in events
    ]


def _phone_input(item: AuthBatchPhoneInput | AuthBatchValidatePhoneInput) -> PhoneInput:
    return PhoneInput(phone_number=item.phone_number, label=item.label)


def _snapshot(batch: AuthBatch, *, include_phone_number: bool) -> AuthBatchSnapshotRead:
    return AuthBatchSnapshotRead(
        batch=_batch_read(batch),
        items=[_item_read(item, include_phone_number=include_phone_number) for item in batch.items],
        server_time=utc_now(),
        poll_again_in_ms=_poll_interval(batch),
    )


def _batch_read(batch: AuthBatch) -> AuthBatchRead:
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


def _item_read(item: AuthBatchItem, *, include_phone_number: bool) -> AuthBatchItemRead:
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


def _can_view_full_phone(auth: AuthContext) -> bool:
    return auth.role in {"operator", "admin", "owner"}


def _require_batch(session: Session, batch_id: str, workspace_id: str | None = None) -> AuthBatch:
    batch = get_batch(session, batch_id, workspace_id=workspace_id)
    if batch is None:
        raise AppError(
            status_code=404,
            error_code="AUTH_BATCH_NOT_FOUND",
            error_class="not_found",
            message="auth batch not found",
        )
    return batch


def _require_item_in_batch(
    session: Session, batch_id: str, item_id: str, workspace_id: str
) -> AuthBatchItem:
    _require_batch(session, batch_id, workspace_id)
    item = session.get(AuthBatchItem, item_id)
    if item is None or item.batch_id != batch_id:
        raise AppError(
            status_code=404,
            error_code="AUTH_BATCH_ITEM_NOT_FOUND",
            error_class="not_found",
            message="auth batch item not found",
        )
    return item


def _poll_interval(batch: AuthBatch) -> int:
    if batch.status in {"completed", "failed", "cancelled"}:
        return 0
    if any(item.status in {"waiting_code", "waiting_2fa"} for item in batch.items):
        return 2000
    if batch.status == "paused":
        return 15000
    return 3000


def _dispatch_or_raise_queue_unavailable(session: Session, batch: AuthBatch) -> None:
    launched = dispatch_once(session, batch.id)
    session.refresh(batch)
    if launched > 0 or not _looks_like_queue_enqueue_failure(batch):
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


def _looks_like_queue_enqueue_failure(batch: AuthBatch) -> bool:
    active_or_waiting = {
        AuthBatchItemStatus.STARTING,
        AuthBatchItemStatus.WAITING_CODE,
        AuthBatchItemStatus.WAITING_2FA,
    }
    has_active_or_waiting = any(item.status in active_or_waiting for item in batch.items)
    has_queue_failure = any(item.error_code == "QUEUE_UNAVAILABLE" for item in batch.items)
    has_queued = any(item.status == AuthBatchItemStatus.QUEUED for item in batch.items)
    return not has_active_or_waiting and (has_queue_failure or has_queued)


def _conflict(message: str) -> AppError:
    return AppError(
        status_code=409,
        error_code="AUTH_BATCH_STATE_CONFLICT",
        error_class="state",
        message=message,
    )
