from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import AccountOperationLogPageRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.operation_logs import list_global_logs

router = APIRouter(prefix="/api/operation-logs", tags=["operation-logs"])
_ALLOWED_QUERY_PARAMS = {"account_id", "operation_type", "status_filter", "limit", "offset"}


def _reject_unknown_query_params(request: Request) -> None:
    unknown = set(request.query_params) - _ALLOWED_QUERY_PARAMS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"unknown query parameter: {sorted(unknown)[0]}",
        )


@router.get("", response_model=AccountOperationLogPageRead)
def get_operation_logs(
    account_id: str | None = None,
    operation_type: str | None = None,
    status_filter: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _valid_query: None = Depends(_reject_unknown_query_params),
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
