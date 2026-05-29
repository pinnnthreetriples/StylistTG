from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.modules.account_safety.status_contracts import AccountStatusObservationRead
from app.modules.account_safety.status_repository import list_status_observations
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get(
    "/{account_id}/status-observations",
    response_model=list[AccountStatusObservationRead],
)
def list_account_status_observations(
    account_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> list[AccountStatusObservationRead]:
    require_account_in_workspace(session, account_id, auth)
    rows = list_status_observations(
        session,
        workspace_id=auth.workspace_id,
        account_id=account_id,
        limit=limit,
    )
    return [AccountStatusObservationRead.model_validate(row) for row in rows]


__all__ = ["router"]
