from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.contracts.account_status import AccountStatusObservationRead
from app.db import get_session
from app.models import AccountStatusObservation
from app.services.auth_context import AuthContext, require_authenticated

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
    rows = session.execute(
        select(AccountStatusObservation)
        .where(AccountStatusObservation.workspace_id == auth.workspace_id)
        .where(AccountStatusObservation.account_id == account_id)
        .order_by(AccountStatusObservation.observed_at.desc())
        .limit(limit)
    ).scalars()
    return [AccountStatusObservationRead.model_validate(row) for row in rows]
