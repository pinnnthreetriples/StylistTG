from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.config import settings
from app.job_queue.rq import enqueue_telegram_auth_action
from app.schemas import (
    TelegramAuthCodeSubmit,
    TelegramAuthPasswordSubmit,
    TelegramAuthSessionCreate,
    TelegramAuthSessionRead,
)
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.telegram_auth_sessions import (
    auth_session_to_dict,
    create_auth_session,
    get_auth_session,
    list_auth_sessions,
    process_auth_action,
)

router = APIRouter(prefix="/api/accounts/auth-sessions", tags=["telegram-auth-sessions"])


@router.post("", response_model=TelegramAuthSessionRead, status_code=status.HTTP_201_CREATED)
def post_auth_session(
    payload: TelegramAuthSessionCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = create_auth_session(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        phone_number=payload.phone_number,
        label=payload.label,
    )
    if not settings.tdlib_live_enabled or not enqueue_telegram_auth_action(
        row.id, row.workspace_id, "start"
    ):
        row = process_auth_action(
            session, auth_session_id=row.id, workspace_id=auth.workspace_id, action="start"
        )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))


@router.get("", response_model=list[TelegramAuthSessionRead])
def get_auth_sessions(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return [
        TelegramAuthSessionRead(**auth_session_to_dict(row))
        for row in list_auth_sessions(session, workspace_id=auth.workspace_id)
    ]


@router.get("/{auth_session_id}", response_model=TelegramAuthSessionRead)
def get_auth_session_status(
    auth_session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    row = get_auth_session(session, auth_session_id=auth_session_id, workspace_id=auth.workspace_id)
    if row is None:
        raise AppError(
            status_code=404,
            error_code="AUTH_SESSION_NOT_FOUND",
            error_class="not_found",
            message="auth session not found",
        )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))


@router.post("/{auth_session_id}/code", response_model=TelegramAuthSessionRead)
def post_auth_session_code(
    auth_session_id: str,
    payload: TelegramAuthCodeSubmit,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = process_auth_action(
        session,
        auth_session_id=auth_session_id,
        workspace_id=auth.workspace_id,
        action="submit_code",
        secret_value=payload.code,
    )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))


@router.post("/{auth_session_id}/password", response_model=TelegramAuthSessionRead)
def post_auth_session_password(
    auth_session_id: str,
    payload: TelegramAuthPasswordSubmit,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = process_auth_action(
        session,
        auth_session_id=auth_session_id,
        workspace_id=auth.workspace_id,
        action="submit_password",
        secret_value=payload.password,
    )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))


@router.post("/{auth_session_id}/cancel", response_model=TelegramAuthSessionRead)
def post_auth_session_cancel(
    auth_session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = process_auth_action(
        session, auth_session_id=auth_session_id, workspace_id=auth.workspace_id, action="cancel"
    )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))
