"""Component scoring helpers for GGR calculation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountProfileState,
    AccountProxy,
    AccountStatusObservation,
    WarmupSession,
    utc_now,
)

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


def _history_score(session: Session, account: Account) -> float:
    """Score based on spamblock history. Constant until the spamblock log table is wired up."""
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
    """Score based on profile completeness from AccountProfileState."""
    ps = session.get(AccountProfileState, account.id)
    if ps is None:
        return 0.0
    filled = sum(1 for v in [ps.first_name, ps.last_name, ps.bio, ps.profile_photo_asset_id] if v)
    return filled / 4


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


__all__ = [
    "WEIGHTS",
    "compute_bucket",
    "compute_components",
    "compute_score",
]
