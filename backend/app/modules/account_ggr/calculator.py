"""GGR (GramGPT Rating) Calculator — composite account survivability score.

Computes a weighted 1.0–10.0 rating from multiple component signals.
Recalculates every 6 hours with max ±1.0 smoothing per cycle.

Phase 2 Task 11 — partial wiring.

Live signals (read from DB):
  - age_score: account.created_at
  - origin_score: account.origin
  - proxy_score: account_proxy status
  - fingerprint_score: account_status_observations.device_model_hash
  - ip_change_score: account_status_observations.proxy_ip_hash
  - session_anomaly_score: latest account_status_observations.consecutive_failures
  - warmup_score: latest WarmupSession
  - profile_score: AccountProfileState

Remaining stub signal:
  - history_score: always 1.0 — TODO integration with SpamBlock log
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountGgrScore,
    new_id,
    utc_now,
)
from app.modules.account_ggr.components import (
    WEIGHTS,
    _age_score,
    _fingerprint_score,
    _history_score,
    _ip_change_score,
    _origin_score,
    _profile_score,
    _proxy_score,
    _session_anomaly_score,
    _warmup_score,
    compute_bucket,
    compute_components,
    compute_score,
)
from app.observability.safety_metrics import safety_metrics

RECALC_INTERVAL = timedelta(hours=6)
MAX_DELTA_PER_CYCLE = 1.0


def _apply_smoothing(new_score: float, previous_score: float | None) -> float:
    """Apply max delta smoothing: ±1.0 per cycle."""
    if previous_score is None:
        return new_score
    delta = new_score - previous_score
    if abs(delta) <= MAX_DELTA_PER_CYCLE:
        return new_score
    if delta > 0:
        return round(previous_score + MAX_DELTA_PER_CYCLE, 1)
    return round(previous_score - MAX_DELTA_PER_CYCLE, 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_ggr(
    session: Session,
    account: Account,
    workspace_id: str,
    *,
    force: bool = False,
) -> AccountGgrScore:
    """Calculate or recalculate GGR for a single account.

    If force=True, recalculates immediately regardless of next_calculation_at.
    Returns the (possibly updated) AccountGgrScore row.
    """
    stmt = select(AccountGgrScore).where(
        AccountGgrScore.workspace_id == workspace_id,
        AccountGgrScore.account_id == account.id,
    )
    ggr_row = session.execute(stmt).scalar_one_or_none()

    now = utc_now()

    if ggr_row and not force:
        if ggr_row.next_calculation_at and ggr_row.next_calculation_at > now:
            return ggr_row

    components = compute_components(session, account)
    raw_score = compute_score(components)

    previous_score = ggr_row.score if ggr_row else None
    previous_bucket = ggr_row.bucket if ggr_row else None
    smoothed_score = _apply_smoothing(raw_score, previous_score)
    # Clamp to valid range
    smoothed_score = max(1.0, min(10.0, smoothed_score))
    bucket = compute_bucket(smoothed_score)

    if ggr_row is None:
        ggr_row = AccountGgrScore(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account.id,
            score=smoothed_score,
            bucket=bucket,
            breakdown_json=components,
            previous_score=None,
            last_calculated_at=now,
            next_calculation_at=now + RECALC_INTERVAL,
            created_at=now,
            updated_at=now,
        )
        session.add(ggr_row)
    else:
        ggr_row.previous_score = previous_score
        ggr_row.score = smoothed_score
        ggr_row.bucket = bucket
        ggr_row.breakdown_json = components
        ggr_row.last_calculated_at = now
        ggr_row.next_calculation_at = now + RECALC_INTERVAL
        ggr_row.updated_at = now

    session.flush()
    safety_metrics.ggr_score(workspace_id=workspace_id, bucket=bucket, score=smoothed_score)
    if bucket != previous_bucket:
        if bucket == "weak":
            safety_metrics.weak_ggr_transition(
                workspace_id=workspace_id,
                from_bucket=previous_bucket or "none",
            )
        if bucket == "weak" or previous_bucket == "weak":
            safety_metrics.weak_ggr_accounts_total(
                workspace_id=workspace_id,
                value=_weak_ggr_account_count(session, workspace_id),
            )
    return ggr_row


def _weak_ggr_account_count(session: Session, workspace_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(AccountGgrScore)
        .where(
            AccountGgrScore.workspace_id == workspace_id,
            AccountGgrScore.bucket == "weak",
        )
    )
    return int(session.execute(stmt).scalar_one())


def get_ggr_score(
    session: Session,
    account_id: str,
    workspace_id: str,
) -> AccountGgrScore | None:
    """Retrieve the current GGR score for an account."""
    stmt = select(AccountGgrScore).where(
        AccountGgrScore.workspace_id == workspace_id,
        AccountGgrScore.account_id == account_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def backfill_ggr_scores(session: Session, workspace_id: str) -> int:
    """Create default GGR records for accounts that don't have one yet.

    Returns the count of newly created records.
    """
    existing_stmt = select(  # nosemgrep: missing-workspace-id-filter-projection - workspace_id predicate is in the .where below.
        AccountGgrScore.account_id
    ).where(AccountGgrScore.workspace_id == workspace_id)
    existing_ids = set(session.execute(existing_stmt).scalars().all())

    accounts_stmt = select(Account).where(Account.workspace_id == workspace_id)
    accounts = session.execute(accounts_stmt).scalars().all()

    created = 0
    now = utc_now()
    for account in accounts:
        if account.id in existing_ids:
            continue
        ggr_row = AccountGgrScore(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account.id,
            score=5.0,
            bucket="medium",
            breakdown_json={},
            previous_score=None,
            last_calculated_at=None,
            next_calculation_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(ggr_row)
        created += 1

    if created:
        session.flush()
    return created


def recalculate_due_scores(session: Session, workspace_id: str, *, limit: int = 100) -> int:
    """Recalculate GGR scores that are due (next_calculation_at <= now).

    Returns count of recalculated scores.
    """
    now = utc_now()
    stmt = (
        select(AccountGgrScore)
        .where(
            AccountGgrScore.workspace_id == workspace_id,
            AccountGgrScore.next_calculation_at <= now,
        )
        .limit(limit)
    )
    due_rows = session.execute(stmt).scalars().all()

    recalculated = 0
    for ggr_row in due_rows:
        account_stmt = select(Account).where(
            Account.id == ggr_row.account_id, Account.workspace_id == workspace_id
        )
        account = session.execute(account_stmt).scalar_one_or_none()
        if account is None:
            continue
        calculate_ggr(session, account, workspace_id, force=True)
        recalculated += 1

    return recalculated


__all__ = [
    "WEIGHTS",
    "RECALC_INTERVAL",
    "MAX_DELTA_PER_CYCLE",
    "_age_score",
    "_apply_smoothing",
    "_fingerprint_score",
    "_history_score",
    "_ip_change_score",
    "_origin_score",
    "_profile_score",
    "_proxy_score",
    "_session_anomaly_score",
    "_warmup_score",
    "compute_components",
    "compute_score",
    "compute_bucket",
    "calculate_ggr",
    "get_ggr_score",
    "backfill_ggr_scores",
    "recalculate_due_scores",
]
