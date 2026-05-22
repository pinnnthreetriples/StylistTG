from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.disaster_state import DisasterState
from app.models import Account, AccountQuarantine


def evaluate_disaster_state(
    session: Session,
    *,
    workspace_id: str,
    now: datetime,
    threshold: float = 0.5,
    window_hours: int = 1,
) -> DisasterState:
    """Compute disaster state for a workspace based on quarantine fraction in window."""

    total_accounts = session.scalar(
        select(func.count()).select_from(Account).where(Account.workspace_id == workspace_id)
    )
    total = int(total_accounts or 0)
    cutoff = now - timedelta(hours=window_hours)
    active_recent_filter = (
        AccountQuarantine.workspace_id == workspace_id,
        AccountQuarantine.released_at.is_(None),
        AccountQuarantine.started_at >= cutoff,
        AccountQuarantine.until > now,
    )
    quarantined_count = int(
        session.scalar(
            select(func.count()).select_from(AccountQuarantine).where(*active_recent_filter)
        )
        or 0
    )
    fraction = round(quarantined_count / total, 4) if total else 0.0
    sample_account_ids = list(
        row.account_id
        for row in session.scalars(
            select(AccountQuarantine)
            .where(AccountQuarantine.workspace_id == workspace_id)
            .where(AccountQuarantine.released_at.is_(None))
            .where(AccountQuarantine.started_at >= cutoff)
            .where(AccountQuarantine.until > now)
            .order_by(AccountQuarantine.started_at.desc(), AccountQuarantine.account_id)
            .limit(5)
        )
    )
    return DisasterState(
        workspace_id=workspace_id,
        is_disaster=fraction > threshold,
        quarantined_count=quarantined_count,
        total_accounts=total,
        quarantined_fraction=fraction,
        threshold=threshold,
        window_hours=window_hours,
        detected_at=now,
        sample_quarantined_account_ids=sample_account_ids,
    )
