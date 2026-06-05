from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.modules.account_survival.contracts import (
    AccountSurvivalMetricRead,
    AccountSurvivalSummaryRead,
)
from app.modules.account_survival.queries import get_account_survival, get_survival_summary
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated

router = APIRouter(prefix="/api/account-survival", tags=["account-survival"])


@router.get("/summary", response_model=AccountSurvivalSummaryRead)
def read_survival_summary(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> AccountSurvivalSummaryRead:
    return get_survival_summary(session, workspace_id=auth.workspace_id)


@router.get("/{account_id}", response_model=AccountSurvivalMetricRead | None)
def read_account_survival(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> AccountSurvivalMetricRead | None:
    require_account_in_workspace(session, account_id, auth)
    return get_account_survival(session, workspace_id=auth.workspace_id, account_id=account_id)
