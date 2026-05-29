from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.api.tenant_helpers import require_account_in_workspace
from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.job_queue.rq import enqueue_telegram_auth_action
from app.logging_utils import log_event
from app.schemas import (
    AccountRuntimeDiagnosticsRead,
    RuntimeRefreshRead,
    TelegramAuthSessionCreate,
    TelegramAuthSessionRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.services.execution_policy import ensure_execution_usable
from app.services.operation_logs import log_operation
from app.services.profile_sync import build_profile_sync_adapter, sync_account_profile_snapshot
from app.services.runtime_diagnostics import account_runtime_diagnostics
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
    try:
        log_event("runtime_refresh_requested", account_id=account_id)
        result = ensure_execution_usable(
            session,
            account_id,
            adapter=build_profile_execution_adapter(),
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    if result.account.account_state == "execution_usable":
        profile_sync_adapter = build_profile_sync_adapter()
        try:
            sync_account_profile_snapshot(session, account_id, adapter=profile_sync_adapter)
            log_operation(
                session,
                account_id=account_id,
                operation_type="sync",
                operation_key="profile_snapshot",
                status="completed",
                severity="info",
                source="runtime_refresh",
                message="Profile snapshot synced",
                workspace_id=auth.workspace_id,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            log_operation(
                session,
                account_id=account_id,
                operation_type="sync",
                operation_key="profile_snapshot",
                status="failed",
                severity="warning",
                source="runtime_refresh",
                message="Profile snapshot sync failed",
                error_code="PROFILE_SYNC_FAILED",
                error_class=exc.__class__.__name__,
                workspace_id=auth.workspace_id,
            )
            session.commit()
            log_event(
                "profile_sync_failed",
                account_id=account_id,
                error_class=exc.__class__.__name__,
            )
            raise AppError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                error_code="PROFILE_SYNC_FAILED",
                error_class="telegram_sync",
                message="Telegram profile sync failed",
                details={"reason": exc.__class__.__name__},
            ) from exc
    diagnostics = account_runtime_diagnostics(session, account_id)
    return RuntimeRefreshRead(
        account_id=result.account.id,
        account_state=result.account.account_state,
        runtime_health=result.runtime_state.runtime_health,
        is_execution_usable=result.account.account_state == "execution_usable",
        last_error_code=diagnostics["last_error_code"],
        last_error_class=diagnostics["last_error_class"],
        refreshed_at=datetime.now(UTC),
    )


@router.get("/{account_id}/runtime-diagnostics", response_model=AccountRuntimeDiagnosticsRead)
def runtime_diagnostics(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        payload = account_runtime_diagnostics(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    return AccountRuntimeDiagnosticsRead(**payload)


__all__ = ["router"]
