from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NeuroCommentCampaign, NeuroCommentGeneratedComment, utc_now
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
)


class ApprovalExpirer:
    """Phase 0 Task 3: expire pending generated comments older than TTL.

    Posts in Telegram lose relevance quickly. Pending approvals must auto-expire
    so the approval queue does not accumulate stale comments and so that downstream
    sender preflight does not attempt to dispatch a comment for a post that is no
    longer relevant.
    """

    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def expire_stale_approvals(
        self,
        session: Session,
        *,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> int:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        moment = now or utc_now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        cutoff = moment - timedelta(seconds=ttl_seconds)
        stmt = (
            select(NeuroCommentGeneratedComment, NeuroCommentCampaign.workspace_id)
            .join(
                NeuroCommentCampaign,
                NeuroCommentGeneratedComment.campaign_id == NeuroCommentCampaign.id,
            )
            .where(
                NeuroCommentGeneratedComment.approval_status
                == NeuroGeneratedApprovalStatus.PENDING.value
            )
            .where(NeuroCommentGeneratedComment.created_at < cutoff)
            .order_by(NeuroCommentGeneratedComment.created_at.asc())
        )
        expired = 0
        for comment, workspace_id in session.execute(stmt).all():
            comment.approval_status = NeuroGeneratedApprovalStatus.EXPIRED.value
            comment.updated_at = moment
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=comment.campaign_id,
                account_id=comment.account_id,
                target_id=comment.target_id,
                observed_post_id=comment.observed_post_id,
                generated_comment_id=comment.id,
                event_type="approval_expired",
                event_level=NeuroEventLevel.WARNING,
                message="generated comment approval expired",
                data={
                    "ttl_seconds": ttl_seconds,
                    "expired_at": moment.isoformat(),
                },
            )
            expired += 1
        session.flush()
        return expired


__all__ = ["ApprovalExpirer"]
