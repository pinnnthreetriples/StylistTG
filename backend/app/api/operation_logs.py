from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import AccountOperationLogPageRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.operation_logs import list_global_logs

router = APIRouter(prefix="/api/operation-logs", tags=["operation-logs"])


@router.get("", response_model=AccountOperationLogPageRead)
def get_operation_logs(
    account_id: str | None = None,
    operation_type: str | None = None,
    status_filter: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return list_global_logs(
        session,
        account_id=account_id,
        operation_type=operation_type,
        status=status_filter,
        limit=limit,
        offset=offset,
        workspace_id=auth.workspace_id,
    )
