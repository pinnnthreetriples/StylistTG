from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import TdlibAuthResult, TdlibAuthStatus, build_tdlib_auth_adapter
from app.models import (
    AccountState,
    AuthAttempt,
    AuthAttemptKind,
    AuthAttemptStatus,
    AuthBatchItem,
    AuthBatchItemStatus,
    utc_now,
)
from app.services.auth_batch_errors import apply_auth_error, parse_flood_wait_seconds
from app.services.auth_batch_state import transition_item


CODE_INPUT_TIMEOUT_SECONDS = 180
MAX_ATTEMPTS = 2


def run_batch_start_auth(session: Session, item_id: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    if item.status != AuthBatchItemStatus.STARTING:
        return item
    _record_attempt(session, item, AuthAttemptKind.START_AUTH, AuthAttemptStatus.STARTED)
    adapter = build_tdlib_auth_adapter()
    result = adapter.start_otp(item.account_id, item.phone_number)
    _materialize_account(item, result)
    _apply_result_to_item(session, item, result, actor="worker")
    item.locked_by = None
    item.lock_expires_at = None
    session.commit()
    session.refresh(item)
    return item


def submit_batch_code(session: Session, item_id: str, code: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    if item.status != AuthBatchItemStatus.WAITING_CODE:
        raise ValueError("item is not waiting for code")
    _record_attempt(session, item, AuthAttemptKind.SUBMIT_CODE, AuthAttemptStatus.STARTED)
    result = build_tdlib_auth_adapter().confirm_otp(item.account_id, code)
    _materialize_account(item, result)
    _apply_result_to_item(session, item, result, actor="user")
    session.commit()
    session.refresh(item)
    return item


def submit_batch_password(session: Session, item_id: str, password: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    if item.status != AuthBatchItemStatus.WAITING_2FA:
        raise ValueError("item is not waiting for 2FA")
    _record_attempt(session, item, AuthAttemptKind.SUBMIT_2FA, AuthAttemptStatus.STARTED)
    result = build_tdlib_auth_adapter().submit_password(item.account_id, password)
    _materialize_account(item, result)
    _apply_result_to_item(session, item, result, actor="user")
    session.commit()
    session.refresh(item)
    return item


def request_new_code(session: Session, item_id: str) -> AuthBatchItem:
    item = _require_item(session, item_id)
    if item.status not in {AuthBatchItemStatus.TIMED_OUT, AuthBatchItemStatus.FAILED}:
        raise ValueError("item cannot request a new code from current state")
    if item.attempt_count >= MAX_ATTEMPTS:
        raise ValueError("maximum attempts reached")
    item.resend_count += 1
    item.error_code = None
    item.error_message = None
    transition_item(item, AuthBatchItemStatus.QUEUED, actor="user")
    session.commit()
    session.refresh(item)
    return item


def _apply_result_to_item(
    session: Session,
    item: AuthBatchItem,
    result: TdlibAuthResult,
    *,
    actor: str,
) -> None:
    attempt = item.attempts[-1] if item.attempts else None
    if result.status == TdlibAuthStatus.WAIT_CODE:
        item.code_expires_at = utc_now() + timedelta(seconds=CODE_INPUT_TIMEOUT_SECONDS)
        item.error_code = None
        item.error_message = None
        transition_item(item, AuthBatchItemStatus.WAITING_CODE, actor=actor)
        if attempt:
            attempt.status = AuthAttemptStatus.SUCCEEDED
            attempt.finished_at = utc_now()
        return
    if result.status == TdlibAuthStatus.WAIT_PASSWORD:
        item.error_code = None
        item.error_message = None
        transition_item(item, AuthBatchItemStatus.WAITING_2FA, actor=actor)
        if attempt:
            attempt.status = AuthAttemptStatus.SUCCEEDED
            attempt.finished_at = utc_now()
        return
    if result.status == TdlibAuthStatus.READY:
        item.error_code = None
        item.error_message = None
        transition_item(item, AuthBatchItemStatus.AUTHORIZED, actor=actor)
        if attempt:
            attempt.status = AuthAttemptStatus.SUCCEEDED
            attempt.finished_at = utc_now()
        return

    new_status = apply_auth_error(item, result.error or result.recovery_marker)
    if new_status == item.status:
        item.updated_at = utc_now()
    else:
        if new_status == AuthBatchItemStatus.QUEUED:
            item.next_retry_at = utc_now() + timedelta(
                seconds=parse_flood_wait_seconds(result.error)
            )
            if item.attempt_count >= MAX_ATTEMPTS:
                new_status = AuthBatchItemStatus.FAILED
        transition_item(item, new_status, actor=actor)
    if attempt:
        attempt.status = AuthAttemptStatus.FAILED
        attempt.error_code = item.error_code
        attempt.error_message = item.error_message
        attempt.finished_at = utc_now()


def _materialize_account(item: AuthBatchItem, result: TdlibAuthResult) -> None:
    account = item.account
    runtime = account.runtime_state
    account.auth_source = "batch"
    account.account_state = result.account_state
    if result.telegram_user_id:
        account.telegram_user_id = result.telegram_user_id
    runtime.session_present = result.session_present
    runtime.runtime_health = result.runtime_health
    runtime.reauth_required = result.reauth_required
    runtime.recovery_marker = result.recovery_marker
    runtime.updated_at = utc_now()
    if result.telegram_user_id:
        runtime.authorized_last_confirmed_at = utc_now()
    if (
        result.status == TdlibAuthStatus.READY
        and account.account_state == AccountState.AUTHORIZED_READY
    ):
        runtime.runtime_health = "ready"


def _record_attempt(
    session: Session,
    item: AuthBatchItem,
    kind: str,
    status: str,
) -> None:
    session.add(
        AuthAttempt(
            batch_item_id=item.id,
            attempt_number=max(item.attempt_count, 1),
            kind=kind,
            status=status,
        )
    )
    session.flush()


def _require_item(session: Session, item_id: str) -> AuthBatchItem:
    item = session.get(AuthBatchItem, item_id)
    if item is None:
        raise ValueError("batch item not found")
    return item
