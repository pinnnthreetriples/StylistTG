from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.modules.account_ggr.contracts import GgrBreakdownRead, GgrBucket, GgrScoreRead
from app.modules.account_ggr.service import calculate_ggr, get_ggr_score
from app.modules.auth.dependencies import AuthContext, require_authenticated

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/ggr", response_model=GgrScoreRead)
def get_account_ggr(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> GgrScoreRead:
    account = require_account_in_workspace(session, account_id, auth)
    ggr_row = get_ggr_score(session, account_id, workspace_id=auth.workspace_id)

    if ggr_row is None:
        ggr_row = calculate_ggr(session, account, workspace_id=auth.workspace_id)
        session.commit()

    breakdown = ggr_row.breakdown_json or {}
    return GgrScoreRead(
        id=ggr_row.id,
        account_id=ggr_row.account_id,
        score=ggr_row.score,
        bucket=cast(GgrBucket, ggr_row.bucket),
        breakdown=GgrBreakdownRead(
            age=breakdown.get("age", 0.0),
            origin=breakdown.get("origin", 0.0),
            history=breakdown.get("history", 0.0),
            proxy=breakdown.get("proxy", 0.0),
            fingerprint=breakdown.get("fingerprint", 0.0),
            ip_change=breakdown.get("ip_change", 0.0),
            session_anomaly=breakdown.get("session_anomaly", 0.0),
            warmup=breakdown.get("warmup", 0.0),
            profile=breakdown.get("profile", 0.0),
        ),
        previous_score=ggr_row.previous_score,
        last_calculated_at=ggr_row.last_calculated_at,
        next_calculation_at=ggr_row.next_calculation_at,
        created_at=ggr_row.created_at,
        updated_at=ggr_row.updated_at,
    )


__all__ = ["router"]
