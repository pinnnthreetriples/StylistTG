"""Per-account stable BehaviorProfile baseline + session randomization."""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AccountBehaviorProfile, WorkspaceSafetyPolicy, new_id, utc_now


# Preset ranges from Section 2.1 of the plan
PRESET_RANGES: dict[str, dict[str, tuple[float, float] | None]] = {
    "conservative": {
        "typing_speed_cpm": (40, 60),
        "typo_rate": (0.06, 0.10),
        "profile_view_probability": (0.85, 0.95),
        "scroll_probability": (0.40, 0.60),
        "message_deletion_probability": (0.02, 0.04),
    },
    "balanced": {
        "typing_speed_cpm": (100, 150),
        "typo_rate": (0.03, 0.07),
        "profile_view_probability": (0.60, 0.80),
        "scroll_probability": (0.20, 0.40),
        "message_deletion_probability": (0.01, 0.03),
    },
    "aggressive": {
        "typing_speed_cpm": None,
        "typo_rate": (0.01, 0.03),
        "profile_view_probability": (0.20, 0.40),
        "scroll_probability": (0.00, 0.10),
        "message_deletion_probability": (0.005, 0.015),
    },
}


def _ranges_from_policy(
    policy: WorkspaceSafetyPolicy,
) -> dict[str, tuple[float, float] | None]:
    """Derive PRESET_RANGES-style dict from a WorkspaceSafetyPolicy row."""
    cpm_min = policy.typing_chars_per_minute_min
    cpm_max = policy.typing_chars_per_minute_max
    typing_range: tuple[float, float] | None = None
    if cpm_min is not None and cpm_max is not None:
        typing_range = (float(cpm_min), float(cpm_max))

    pvp = policy.profile_view_probability or 0.7
    sp = policy.scroll_probability or 0.3
    tp = policy.typo_probability or 0.05
    mdp = policy.message_deletion_probability or 0.02

    return {
        "typing_speed_cpm": typing_range,
        "typo_rate": (tp * 0.8, tp * 1.2),
        "profile_view_probability": (pvp * 0.9, min(1.0, pvp * 1.1)),
        "scroll_probability": (max(0.0, sp * 0.8), min(1.0, sp * 1.2)),
        "message_deletion_probability": (mdp * 0.8, mdp * 1.2),
    }


@dataclass(frozen=True)
class SessionProfile:
    """Randomized per-session variant of the stable baseline (±10%)."""

    typing_speed_cpm: float | None
    typo_rate: float
    profile_view_probability: float
    scroll_probability: float
    message_deletion_probability: float
    action_sequence_seed: int


def _resolve_ranges(
    session: Session,
    workspace_id: str,
    preset: str,
) -> dict[str, tuple[float, float] | None]:
    """Resolve baseline ranges: prefer WorkspaceSafetyPolicy, fall back to preset."""
    from sqlalchemy import select

    policy = session.execute(
        select(WorkspaceSafetyPolicy).where(WorkspaceSafetyPolicy.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if policy is not None:
        return _ranges_from_policy(policy)
    return PRESET_RANGES.get(preset, PRESET_RANGES["balanced"])


def get_or_create_baseline(
    session: Session,
    account_id: str,
    workspace_id: str,
    preset: str = "balanced",
    *,
    rng: random.Random | None = None,
) -> AccountBehaviorProfile:
    """Return the existing baseline or create one from workspace policy / preset ranges.

    The baseline is stable per-account: once created it never changes
    (except through explicit admin override or deletion).
    """
    existing = (
        session.query(AccountBehaviorProfile)
        .filter_by(workspace_id=workspace_id, account_id=account_id)
        .first()
    )
    if existing is not None:
        return existing

    ranges = _resolve_ranges(session, workspace_id, preset)
    r = rng or random.Random()

    typing_range = ranges.get("typing_speed_cpm")
    typing_cpm: int | None = None
    if typing_range is not None:
        typing_cpm = int(r.uniform(*typing_range))

    typo_range = ranges["typo_rate"]
    pvp_range = ranges["profile_view_probability"]
    sp_range = ranges["scroll_probability"]
    mdp_range = ranges["message_deletion_probability"]
    assert typo_range is not None and pvp_range is not None
    assert sp_range is not None and mdp_range is not None

    profile = AccountBehaviorProfile(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        typing_speed_baseline_cpm=typing_cpm,
        typo_rate_baseline=round(r.uniform(*typo_range), 4),
        profile_view_probability_baseline=round(r.uniform(*pvp_range), 4),
        scroll_probability_baseline=round(r.uniform(*sp_range), 4),
        message_deletion_probability_baseline=round(r.uniform(*mdp_range), 4),
        action_sequence_seed=r.randint(0, 2**31 - 1),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(profile)
    session.flush()
    return profile


def randomize_for_session(
    baseline: AccountBehaviorProfile,
    *,
    rng: random.Random | None = None,
) -> SessionProfile:
    """Derive session-specific values: baseline ±10% for each param."""
    r = rng or random.Random()

    def jitter(value: float) -> float:
        lo = value * 0.9
        hi = value * 1.1
        return r.uniform(lo, hi)

    typing_cpm: float | None = None
    if baseline.typing_speed_baseline_cpm is not None:
        typing_cpm = jitter(float(baseline.typing_speed_baseline_cpm))

    return SessionProfile(
        typing_speed_cpm=typing_cpm,
        typo_rate=max(0.0, min(1.0, jitter(baseline.typo_rate_baseline))),
        profile_view_probability=max(
            0.0, min(1.0, jitter(baseline.profile_view_probability_baseline))
        ),
        scroll_probability=max(0.0, min(1.0, jitter(baseline.scroll_probability_baseline))),
        message_deletion_probability=max(
            0.0, min(1.0, jitter(baseline.message_deletion_probability_baseline))
        ),
        action_sequence_seed=baseline.action_sequence_seed,
    )


__all__ = [
    "PRESET_RANGES",
    "SessionProfile",
    "get_or_create_baseline",
    "randomize_for_session",
]
