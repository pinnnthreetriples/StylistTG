from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStatusObservation


def list_status_observations(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    limit: int,
) -> list[AccountStatusObservation]:
    return list(
        session.execute(
            select(AccountStatusObservation)
            .where(AccountStatusObservation.workspace_id == workspace_id)
            .where(AccountStatusObservation.account_id == account_id)
            .order_by(AccountStatusObservation.observed_at.desc())
            .limit(limit)
        ).scalars()
    )


__all__ = ["list_status_observations"]
