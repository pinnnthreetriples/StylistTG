from __future__ import annotations

from sqlalchemy.orm import Session, object_session

from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentGeneratedComment,
    NeuroCommentTarget,
)
from app.modules.neuro_commenting.enums import NeuroAttemptStatus, NeuroEventLevel
from app.modules.neuro_commenting.limits_service import LimitsService
from app.modules.neuro_commenting.rate_limiter import (
    NeuroCommentRateLimiter,
    RateLimitReservation,
    RateLimitScope,
)
from app.modules.neuro_commenting.sender_contracts import _SendContext


class SenderReservationMixin:
    def _reserve_for_attempt(
        self, session: Session, *, context: _SendContext, workspace_id: str
    ) -> RateLimitReservation | None:
        if not getattr(self._config, "neuro_comment_require_redis_limiter_for_send", True):
            return None
        limiter = self._limiter or self._limiter_for_send(session, context.campaign)
        reservation = limiter.reserve(
            RateLimitScope(
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=context.attempt.account_id or context.comment.account_id,
                target_id=context.attempt.target_id or context.comment.target_id,
            )
        )
        if not reservation.allowed:
            context.attempt.status = NeuroAttemptStatus.SKIPPED.value
            context.attempt.error_code = "RATE_LIMIT_DENIED"
            context.attempt.error_message = reservation.reason
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=context.attempt.account_id,
                target_id=context.attempt.target_id,
                observed_post_id=context.attempt.observed_post_id,
                generated_comment_id=context.comment.id,
                attempt_id=context.attempt.id,
                event_type="rate_limit_denied",
                event_level=NeuroEventLevel.WARNING,
                message=reservation.reason or "rate limit denied",
                data={"checked_limits": reservation.checked_limits},
            )
            return None
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=context.attempt.account_id,
            target_id=context.attempt.target_id,
            observed_post_id=context.attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type="rate_limit_reserved",
            message="neuro-comment send rate limit reserved",
            data={"reservation_id": reservation.reservation_id},
        )
        return reservation

    def _commit_reservation(self, reservation: RateLimitReservation | None) -> None:
        if reservation is None:
            return
        limiter = self._limiter or NeuroCommentRateLimiter(redis_client=self._redis_client)
        limiter.commit(reservation)

    def _rollback_reservation(self, reservation: RateLimitReservation | None) -> None:
        if reservation is None:
            return
        limiter = self._limiter or NeuroCommentRateLimiter(redis_client=self._redis_client)
        limiter.rollback(reservation)

    def _limiter_for_send(
        self, session: Session | None, campaign: NeuroCommentCampaign
    ) -> NeuroCommentRateLimiter:
        limits = None
        if session is not None:
            limits = [
                {
                    "scope_type": item.scope_type,
                    "scope_id": item.scope_id,
                    "limit_type": item.limit_type,
                    "max_value": item.max_value,
                    "window_seconds": item.window_seconds,
                }
                for item in LimitsService().resolve_effective_limits(
                    session, campaign_id=campaign.id, workspace_id=campaign.workspace_id
                )
                if item.enabled
            ]
        return NeuroCommentRateLimiter(redis_client=self._redis_client, limits=limits)

    def _session_for(
        self,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
        campaign: NeuroCommentCampaign,
    ) -> Session | None:
        return object_session(attempt) or object_session(comment) or object_session(campaign)

    def _target_for_send(
        self,
        session: Session | None,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
    ) -> NeuroCommentTarget | None:
        target_id = attempt.target_id or comment.target_id
        if session is None or target_id is None:
            return None
        return (
            session.query(NeuroCommentTarget)
            .filter(
                NeuroCommentTarget.id == target_id,
                NeuroCommentTarget.campaign_id == campaign.id,
            )
            .one_or_none()
        )
