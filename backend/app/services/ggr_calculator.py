"""GGR (GramGPT Rating) Calculator — composite account survivability score.

Computes a weighted 1.0–10.0 rating from multiple component signals.
Recalculates every 6 hours with max ±1.0 smoothing per cycle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountGgrScore,
    new_id,
    utc_now,
)

# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "age": 0.20,
    "origin": 0.10,
    "history": 0.15,
    "proxy": 0.15,
    "fingerprint": 0.10,
    "ip_change": 0.10,
    "session_anomaly": 0.10,
    "warmup": 0.05,
    "profile": 0.05,
}

RECALC_INTERVAL = timedelta(hours=6)
MAX_DELTA_PER_CYCLE = 1.0


# ---------------------------------------------------------------------------
# Component scoring functions (each returns 0.0–1.0)
# ---------------------------------------------------------------------------


def _age_score(account: Account) -> float:
    """Score based on account age."""
    if not account.created_at:
        return 0.0
    now = datetime.now(UTC)
    age = now - account.created_at.replace(tzinfo=UTC) if account.created_at.tzinfo is None else now - account.created_at
    days = age.total_seconds() / 86400
    if days < 1:
        return 0.0
    if days < 7:
        return 0.5
    if days < 30:
        return 0.8
    return 1.0


def _origin_score(account: Account) -> float:
    """Score based on account origin type."""
    origin = getattr(account, "origin", None) or "imported"
    origin_map: dict[str, float] = {
        "created": 0.9,
        "imported": 0.7,
        "bought": 0.5,
    }
    return origin_map.get(origin, 0.7)


def _history_score(account: Account) -> float:
    """Score based on spamblock history: 1.0 - min(1.0, spamblock_count / 5)."""
    spamblock_count = getattr(account, "spamblock_count", 0) or 0
    return 1.0 - min(1.0, spamblock_count / 5)


def _proxy_score(account: Account) -> float:
    """Score based on proxy health status."""
    proxy_status = getattr(account, "proxy_status", None)
    if proxy_status == "healthy":
        return 1.0
    if proxy_status == "failed":
        return 0.0
    return 0.5


def _fingerprint_score(account: Account) -> float:
    """Score based on device fingerprint stability.

    1.0 if device_model_hash stable 7+ days, 0.5 otherwise.
    Simplified: checks if fingerprint_stable_since exists and is > 7 days ago.
    """
    stable_since = getattr(account, "fingerprint_stable_since", None)
    if stable_since is None:
        return 0.5
    now = datetime.now(UTC)
    if stable_since.tzinfo is None:
        stable_since = stable_since.replace(tzinfo=UTC)
    if (now - stable_since).days >= 7:
        return 1.0
    return 0.5


def _ip_change_score(account: Account) -> float:
    """Score based on IP changes in last 24h: 1.0 - min(1.0, ip_changes_24h / 10)."""
    ip_changes = getattr(account, "ip_changes_24h", 0) or 0
    return 1.0 - min(1.0, ip_changes / 10)


def _session_anomaly_score(account: Account) -> float:
    """Score based on session anomalies in last 7d: 1.0 - min(1.0, anomalies_7d / 10)."""
    anomalies = getattr(account, "anomalies_7d", 0) or 0
    return 1.0 - min(1.0, anomalies / 10)


def _warmup_score(account: Account) -> float:
    """Score based on warmup status."""
    warmup_status = getattr(account, "warmup_status", None)
    if warmup_status == "completed":
        return 1.0
    if warmup_status == "in_progress":
        return 0.5
    return 0.0


def _profile_score(account: Account) -> float:
    """Score based on profile completeness (bio + name + photo = 3/3)."""
    completeness = 0
    if getattr(account, "display_name", None):
        completeness += 1
    if getattr(account, "bio", None):
        completeness += 1
    if getattr(account, "profile_photo_asset_id", None):
        completeness += 1
    return completeness / 3


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

COMPONENT_FUNCTIONS: dict[str, Any] = {
    "age": _age_score,
    "origin": _origin_score,
    "history": _history_score,
    "proxy": _proxy_score,
    "fingerprint": _fingerprint_score,
    "ip_change": _ip_change_score,
    "session_anomaly": _session_anomaly_score,
    "warmup": _warmup_score,
    "profile": _profile_score,
}


def compute_components(account: Account) -> dict[str, float]:
    """Compute all component scores for an account."""
    return {key: fn(account) for key, fn in COMPONENT_FUNCTIONS.items()}


def compute_score(components: dict[str, float]) -> float:
    """Compute final GGR score from component values."""
    total = sum(WEIGHTS[k] * components[k] for k in WEIGHTS)
    return round(1.0 + 9.0 * total, 1)


def compute_bucket(score: float) -> str:
    """Determine bucket from score."""
    if score >= 7.0:
        return "strong"
    if score >= 4.0:
        return "medium"
    return "weak"


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

    components = compute_components(account)
    raw_score = compute_score(components)

    previous_score = ggr_row.score if ggr_row else None
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
    return ggr_row


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
    existing_stmt = select(AccountGgrScore.account_id).where(
        AccountGgrScore.workspace_id == workspace_id
    )
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
        account_stmt = select(Account).where(Account.id == ggr_row.account_id)
        account = session.execute(account_stmt).scalar_one_or_none()
        if account is None:
            continue
        calculate_ggr(session, account, workspace_id, force=True)
        recalculated += 1

    return recalculated
