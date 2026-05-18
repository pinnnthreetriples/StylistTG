from __future__ import annotations

from dataclasses import dataclass

from app.models import NeuroCommentCampaign, NeuroCommentCampaignAccount, NeuroCommentTarget


@dataclass(frozen=True)
class RateLimitReservation:
    reservation_id: str | None
    allowed: bool
    reason: str | None = None


class NeuroCommentRateLimiter:
    async def reserve(
        self,
        *,
        campaign: NeuroCommentCampaign,
        account: NeuroCommentCampaignAccount | None,
        target: NeuroCommentTarget | None,
    ) -> RateLimitReservation:
        return RateLimitReservation(reservation_id=None, allowed=True)

    async def commit(self, reservation: RateLimitReservation) -> None:
        return None

    async def rollback(self, reservation: RateLimitReservation) -> None:
        return None
