from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Account, utc_now
from app.modules.account_profile_completeness.contracts import ProfileCompletenessReport

REQUIRED_FIELDS = ("first_name", "bio", "profile_photo_asset_id")
RECOMMENDED_FIELDS = ("username", "pinned_channel_ref")

_WEIGHTS = {
    "first_name": 0.30,
    "bio": 0.30,
    "profile_photo_asset_id": 0.20,
    "username": 0.10,
    "pinned_channel_ref": 0.10,
}


class ProfileCompletenessAccountNotFound(LookupError):
    """Raised when an account is absent or outside the requested workspace."""


def evaluate(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
) -> ProfileCompletenessReport:
    account = (
        session.execute(
            select(Account)
            .where(Account.workspace_id == workspace_id)
            .where(Account.id == account_id)
            .options(joinedload(Account.profile_state))
        )
        .scalars()
        .unique()
        .first()
    )
    if account is None:
        raise ProfileCompletenessAccountNotFound("account not found")

    profile = account.profile_state
    breakdown = {
        "first_name": _has_min_length(profile.first_name if profile else None, 2),
        "bio": _has_min_length(profile.bio if profile else None, 10),
        "profile_photo_asset_id": bool(profile and profile.profile_photo_asset_id),
        "username": bool(profile and profile.username and profile.username.strip()),
        "pinned_channel_ref": bool(account.pinned_channel_ref),
    }
    score = round(sum(_WEIGHTS[field] for field, met in breakdown.items() if met), 2)

    return ProfileCompletenessReport(
        account_id=UUID(account.id),
        score=score,
        breakdown=breakdown,
        missing_required=[field for field in REQUIRED_FIELDS if not breakdown[field]],
        missing_recommended=[field for field in RECOMMENDED_FIELDS if not breakdown[field]],
        evaluated_at=utc_now(),
    )


def _has_min_length(value: str | None, minimum: int) -> bool:
    return value is not None and len(value.strip()) >= minimum


__all__ = [
    "ProfileCompletenessAccountNotFound",
    "ProfileCompletenessReport",
    "evaluate",
]
