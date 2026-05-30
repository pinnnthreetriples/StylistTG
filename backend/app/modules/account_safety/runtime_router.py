from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.config import settings
from app.db import get_session
from app.job_queue.rq import enqueue_telegram_auth_action
from app.modules.account_shared.interfaces import (
    get_runtime_diagnostics,
    refresh_account_runtime,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.schemas import (
    AccountRuntimeDiagnosticsRead,
    RuntimeRefreshRead,
    TelegramAuthSessionCreate,
    TelegramAuthSessionRead,
)
from app.services.telegram_auth_sessions import (
    auth_session_to_dict,
    create_auth_session,
    process_auth_action,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post(
    "/{account_id}/reauth-sessions",
    response_model=TelegramAuthSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def post_account_reauth_session(
    account_id: str,
    payload: TelegramAuthSessionCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    row = create_auth_session(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        phone_number=payload.phone_number,
        label=payload.label,
        source="reauth",
        account_id=account_id,
    )
    if not settings.tdlib_live_enabled or not enqueue_telegram_auth_action(
        row.id, row.workspace_id, "start"
    ):
        row = process_auth_action(
            session, auth_session_id=row.id, workspace_id=auth.workspace_id, action="start"
        )
    return TelegramAuthSessionRead(**auth_session_to_dict(row))


@router.post("/{account_id}/refresh-runtime", response_model=RuntimeRefreshRead)
def refresh_runtime(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    return refresh_account_runtime(session, account_id=account_id, workspace_id=auth.workspace_id)


@router.get("/{account_id}/runtime-diagnostics", response_model=AccountRuntimeDiagnosticsRead)
def runtime_diagnostics(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return get_runtime_diagnostics(session, account_id)


__all__ = ["router"]
