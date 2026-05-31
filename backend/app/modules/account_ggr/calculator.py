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

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountGgrScore,
    AccountProfileState,
    AccountProxy,
    AccountStatusObservation,
    WarmupSession,
    new_id,
    utc_now,
)
from app.observability.safety_metrics import safety_metrics

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
    now = utc_now()
    age = (
        now - account.created_at.replace(tzinfo=UTC)
        if account.created_at.tzinfo is None
        else now - account.created_at
    )
    days = age.total_seconds() / 86400
    if days < 1:
        return 0.0
    if days < 7:
        return 0.5
    if days < 30:
        return 0.8
    return 1.0


def _origin_score(session: Session, account: Account) -> float:
    """Score based on account origin type."""
    mapping = {"created": 1.0, "imported": 0.7, "bought": 0.4}
    return mapping.get(account.origin, 0.7)


# Returns a constant 1.0 until the SpamBlock-log infrastructure exists;
# tracked in the GGR roadmap, not currently scheduled.
def _history_score(session: Session, account: Account) -> float:
    """Score based on spamblock history. Constant 1.0 until the spamblock log table is wired up."""
    return 1.0


def _proxy_score(session: Session, account: Account) -> float:
    """Score based on proxy health status from account_proxy table."""
    proxy = session.get(AccountProxy, account.id)
    if proxy is None:
        return 0.5
    status = proxy.status or "unknown"
    if status in ("tcp_working", "tdlib_working"):
        return 1.0
    if status in ("failed", "tdlib_failed"):
        return 0.0
    return 0.5


def _fingerprint_score(session: Session, account: Account) -> float:
    """Score based on device fingerprint stability over the last 24 hours."""
    scores = _status_observation_component_scores(_status_observations(session, account))
    return scores["fingerprint"]


def _fingerprint_score_from_count(unique_hashes: int) -> float:
    if unique_hashes == 0:
        return 0.5
    if unique_hashes == 1:
        return 1.0
    if unique_hashes == 2:
        return 0.6
    return 0.2


def _ip_change_score(session: Session, account: Account) -> float:
    """Score based on proxy IP stability over the last 24 hours."""
    scores = _status_observation_component_scores(_status_observations(session, account))
    return scores["ip_change"]


def _ip_change_score_from_count(unique_hashes: int) -> float:
    if unique_hashes == 0:
        return 0.5
    if unique_hashes == 1:
        return 1.0
    if unique_hashes == 2:
        return 0.7
    if unique_hashes == 3:
        return 0.4
    return 0.1


def _session_anomaly_score(session: Session, account: Account) -> float:
    """Score based on latest account status consecutive failures."""
    scores = _status_observation_component_scores(_status_observations(session, account))
    return scores["session_anomaly"]


def _session_anomaly_score_from_failures(latest: int | None) -> float:
    if latest is None:
        return 0.5
    if latest == 0:
        return 1.0
    if latest <= 2:
        return 0.7
    if latest <= 4:
        return 0.4
    return 0.1


def _status_observations(
    session: Session,
    account: Account,
    *,
    limit: int = 100,
) -> list[AccountStatusObservation]:
    return list(
        session.execute(
            select(AccountStatusObservation)
            .where(AccountStatusObservation.workspace_id == account.workspace_id)
            .where(AccountStatusObservation.account_id == account.id)
            .order_by(AccountStatusObservation.observed_at.desc())
            .limit(limit)
        ).scalars()
    )


def _status_observation_component_scores(
    observations: list[AccountStatusObservation],
) -> dict[str, float]:
    window_start = utc_now() - timedelta(hours=24)
    recent = [
        observation
        for observation in observations
        if _as_utc(observation.observed_at) >= window_start
    ]
    device_hashes = {
        observation.device_model_hash
        for observation in recent
        if observation.device_model_hash is not None
    }
    proxy_hashes = {
        observation.proxy_ip_hash for observation in recent if observation.proxy_ip_hash is not None
    }
    latest_failures = observations[0].consecutive_failures if observations else None
    return {
        "fingerprint": _fingerprint_score_from_count(len(device_hashes)),
        "ip_change": _ip_change_score_from_count(len(proxy_hashes)),
        "session_anomaly": _session_anomaly_score_from_failures(latest_failures),
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _warmup_score(session: Session, account: Account) -> float:
    """Score based on latest WarmupSession status."""
    stmt = (
        select(WarmupSession)
        .where(WarmupSession.workspace_id == account.workspace_id)
        .where(WarmupSession.account_id == account.id)
        .order_by(WarmupSession.created_at.desc())
        .limit(1)
    )
    ws = session.execute(stmt).scalar_one_or_none()
    if ws is None:
        return 0.0
    if ws.status == "completed":
        return 1.0
    if ws.status in ("active", "scheduled", "validating"):
        return 0.5
    return 0.0


def _profile_score(session: Session, account: Account) -> float:
    """Score based on profile completeness from AccountProfileState (4 fields)."""
    ps = session.get(AccountProfileState, account.id)
    if ps is None:
        return 0.0
    filled = sum(1 for v in [ps.first_name, ps.last_name, ps.bio, ps.profile_photo_asset_id] if v)
    return filled / 4


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

_SESSION_COMPONENT_FUNCTIONS: dict[str, Any] = {
    "origin": _origin_score,
    "history": _history_score,
    "proxy": _proxy_score,
    "fingerprint": _fingerprint_score,
    "ip_change": _ip_change_score,
    "session_anomaly": _session_anomaly_score,
    "warmup": _warmup_score,
    "profile": _profile_score,
}


def compute_components(session: Session, account: Account) -> dict[str, float]:
    """Compute all component scores for an account."""
    result: dict[str, float] = {"age": _age_score(account)}
    status_scores = _status_observation_component_scores(_status_observations(session, account))
    for key, fn in _SESSION_COMPONENT_FUNCTIONS.items():
        if key in status_scores:
            continue
        result[key] = fn(session, account)
    result.update(status_scores)
    return result


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
    "compute_components",
    "compute_score",
    "compute_bucket",
    "calculate_ggr",
    "get_ggr_score",
    "backfill_ggr_scores",
    "recalculate_due_scores",
]
