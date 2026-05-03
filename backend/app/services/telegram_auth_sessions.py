from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.errors import AppError
from app.models import AccountState, TelegramAuthSession, new_id, utc_now
from app.services.account_cooldowns import create_cooldown_from_error
from app.services.accounts import create_account, get_account
from app.services.sensitive_audit import record_sensitive_audit_event
from app.services.tdlib_auth import TdlibAuthStateMachine, TdlibAuthTransition
from app.services.tdlib_client import MockTdlibJsonClient
from app.services.tdlib_paths import build_account_tdlib_paths, build_auth_session_tdlib_paths
from app.services.tdlib_runtime import detect_tdlib_runtime


SAFE_AUTH_ACTIONS = {"start", "submit_code", "submit_password", "cancel"}


def create_auth_session(
    session: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    phone_number: str,
    label: str | None = None,
    source: str = "new_auth",
    account_id: str | None = None,
) -> TelegramAuthSession:
    if account_id and get_account(session, account_id, workspace_id=workspace_id) is None:
        raise AppError(status_code=404, error_code="ACCOUNT_NOT_FOUND", error_class="not_found", message="account not found")
    row = TelegramAuthSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        phone_hint=_phone_hint(phone_number),
        label=label,
        status="created",
        source=source,
        tdlib_storage_key=None,
        requires_code=False,
        requires_password=False,
        created_by_user_id=actor_user_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    paths = (
        build_account_tdlib_paths(workspace_id=workspace_id, account_id=account_id)
        if account_id
        else build_auth_session_tdlib_paths(workspace_id=workspace_id, auth_session_id=row.id)
    )
    row.tdlib_storage_key = paths.storage_key
    session.add(row)
    record_sensitive_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="telegram.auth.started" if source != "reauth" else "telegram.reauth.started",
        entity_type="telegram_auth_session",
        entity_id=row.id,
        account_id=account_id,
        metadata={"source": source, "phone_hint": row.phone_hint, "tdlib_storage_isolated": True},
    )
    session.commit()
    session.refresh(row)
    return row


def list_auth_sessions(session: Session, *, workspace_id: str, limit: int = 50) -> list[TelegramAuthSession]:
    return list(
        session.execute(
            select(TelegramAuthSession)
            .where(TelegramAuthSession.workspace_id == workspace_id)
            .order_by(TelegramAuthSession.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def get_auth_session(session: Session, *, auth_session_id: str, workspace_id: str) -> TelegramAuthSession | None:
    return session.execute(
        select(TelegramAuthSession).where(
            TelegramAuthSession.id == auth_session_id,
            TelegramAuthSession.workspace_id == workspace_id,
        )
    ).scalars().first()


def process_auth_action(
    session: Session,
    *,
    auth_session_id: str,
    workspace_id: str,
    action: str,
    secret_value: str | None = None,
    config: Settings = settings,
) -> TelegramAuthSession:
    if action not in SAFE_AUTH_ACTIONS:
        raise ValueError("unsupported auth action")
    row = _require_session(session, auth_session_id, workspace_id)
    runtime = detect_tdlib_runtime(config)
    if not config.tdlib_live_enabled:
        _fail(row, "tdlib_live_disabled", "TDLib live auth is disabled.")
        _audit_action(session, row, action, {"runtime": runtime.to_safe_dict()})
        session.commit()
        return row
    if not runtime.configured:
        _fail(row, runtime.error_code or "tdlib_not_configured", "TDLib runtime is not configured.")
        _audit_action(session, row, action, {"runtime": runtime.to_safe_dict()})
        session.commit()
        return row

    machine = TdlibAuthStateMachine(MockTdlibJsonClient())
    if action == "start":
        transition = machine.start(phone_number=row.phone_hint or "")
    elif action == "submit_code":
        transition = machine.submit_code(code=secret_value or "")
    elif action == "submit_password":
        transition = machine.submit_password(password=secret_value or "")
    else:
        transition = machine.cancel()
    _apply_transition(session, row, transition, config=config)
    _audit_action(session, row, action, {"transition": transition.status})
    session.commit()
    session.refresh(row)
    return row


def auth_session_to_dict(row: TelegramAuthSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "account_id": row.account_id,
        "phone_hint": row.phone_hint,
        "label": row.label,
        "status": row.status,
        "source": row.source,
        "requires_code": row.requires_code,
        "requires_password": row.requires_password,
        "cooldown_until": row.cooldown_until,
        "last_error_code": row.last_error_code,
        "last_error_message": row.last_error_message,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "completed_at": row.completed_at,
        "failed_at": row.failed_at,
    }


def _apply_transition(session: Session, row: TelegramAuthSession, transition: TdlibAuthTransition, *, config: Settings) -> None:
    row.status = transition.status
    row.requires_code = transition.requires_code
    row.requires_password = transition.requires_password
    row.last_error_code = transition.error_code
    row.last_error_message = transition.error_message
    row.updated_at = utc_now()
    if transition.flood_wait_seconds:
        row.cooldown_until = utc_now() + timedelta(seconds=transition.flood_wait_seconds)
        if row.account_id:
            create_cooldown_from_error(
                session,
                account_id=row.account_id,
                operation="account.auth",
                error_code=f"FLOOD_WAIT_{transition.flood_wait_seconds}",
                source_job_id=row.id,
            )
    if transition.status == "ready":
        row.completed_at = utc_now()
        _link_ready_account(session, row, transition.me or {}, config=config)
    if transition.status == "failed":
        row.failed_at = utc_now()


def _link_ready_account(session: Session, row: TelegramAuthSession, me: dict[str, Any], *, config: Settings) -> None:
    account = get_account(session, row.account_id, workspace_id=row.workspace_id) if row.account_id else None
    if account is None:
        external_ref = f"telegram:{me.get('id') or row.id}"
        account = create_account(
            session,
            external_ref=external_ref,
            telegram_user_id=str(me.get("id")) if me.get("id") is not None else None,
            auth_source="tdlib_live_auth",
            workspace_id=row.workspace_id,
            actor_user_id=row.created_by_user_id,
        )
        row.account_id = account.id
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ok"
    account.runtime_state.reauth_required = False
    account.runtime_state.authorized_last_confirmed_at = utc_now()
    build_account_tdlib_paths(workspace_id=row.workspace_id, account_id=account.id, config=config)


def _require_session(session: Session, auth_session_id: str, workspace_id: str) -> TelegramAuthSession:
    row = get_auth_session(session, auth_session_id=auth_session_id, workspace_id=workspace_id)
    if row is None:
        raise AppError(status_code=404, error_code="AUTH_SESSION_NOT_FOUND", error_class="not_found", message="auth session not found")
    return row


def _fail(row: TelegramAuthSession, code: str, message: str) -> None:
    row.status = "failed"
    row.requires_code = False
    row.requires_password = False
    row.last_error_code = code
    row.last_error_message = message
    row.failed_at = utc_now()
    row.updated_at = utc_now()


def _audit_action(session: Session, row: TelegramAuthSession, action: str, metadata: dict[str, Any]) -> None:
    record_sensitive_audit_event(
        session,
        workspace_id=row.workspace_id,
        actor_user_id=row.created_by_user_id,
        action=f"telegram.auth.{action}",
        entity_type="telegram_auth_session",
        entity_id=row.id,
        account_id=row.account_id,
        metadata=metadata,
    )


def _phone_hint(phone_number: str) -> str:
    digits = "".join(ch for ch in phone_number if ch.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
