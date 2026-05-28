from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.schemas import (
    AccountOperationLogPageRead,
    SensitiveAuditEventPageRead,
    SensitiveAuditEventRead,
)
from app.services.operation_logs import list_account_logs
from app.services.sensitive_audit import audit_event_to_dict, list_sensitive_audit_events

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/audit-events", response_model=SensitiveAuditEventPageRead)
def get_account_audit_events(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    rows, total = list_sensitive_audit_events(
        session,
        workspace_id=auth.workspace_id,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
    return SensitiveAuditEventPageRead(
        items=[SensitiveAuditEventRead(**audit_event_to_dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{account_id}/operation-logs", response_model=AccountOperationLogPageRead)
def get_account_operation_logs(
    account_id: str,
    operation_type: str | None = None,
    status_filter: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return list_account_logs(
            session,
            account_id,
            operation_type=operation_type,
            status=status_filter,
            limit=limit,
            offset=offset,
            workspace_id=auth.workspace_id,
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc


__all__ = ["router"]
