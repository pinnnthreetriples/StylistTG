from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAccountStats,
    NeuroCommentCampaign,
    NeuroCommentChannelStats,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentTarget,
    new_id,
)
from app.services.neuro_commenting.enums import NeuroEventLevel
from app.services.neuro_commenting.repository import safe_event_data


class AnalyticsService:
    def write_event(
        self,
        session: Session,
        *,
        workspace_id: str,
        event_type: str,
        message: str,
        event_level: NeuroEventLevel = NeuroEventLevel.INFO,
        campaign_id: str | None = None,
        account_id: str | None = None,
        target_id: str | None = None,
        observed_post_id: str | None = None,
        generated_comment_id: str | None = None,
        attempt_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> NeuroCommentEvent:
        event = NeuroCommentEvent(
            id=new_id(),
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            account_id=account_id,
            target_id=target_id,
            observed_post_id=observed_post_id,
            generated_comment_id=generated_comment_id,
            attempt_id=attempt_id,
            event_type=event_type,
            event_level=event_level.value,
            message=message,
            data_json=safe_event_data(data),
        )
        session.add(event)
        return event

    def record_generated_comment(
        self,
        session: Session,
        *,
        campaign: NeuroCommentCampaign,
        target: NeuroCommentTarget | None,
        comment: NeuroCommentGeneratedComment,
    ) -> None:
        if target is not None:
            channel_stats = self._channel_stats(
                session, campaign_id=campaign.id, target_id=target.id
            )
            channel_stats.comments_generated = (channel_stats.comments_generated or 0) + 1
        if comment.account_id is not None:
            account_stats = self._account_stats(
                session,
                campaign_id=campaign.id,
                account_id=comment.account_id,
            )
            account_stats.comments_generated = (account_stats.comments_generated or 0) + 1

    def campaign_stats(self, session: Session, *, campaign_id: str) -> dict[str, int]:
        generated = (
            session.query(NeuroCommentGeneratedComment)
            .filter(NeuroCommentGeneratedComment.campaign_id == campaign_id)
            .count()
        )
        return {"comments_generated": int(generated)}

    def _channel_stats(
        self,
        session: Session,
        *,
        campaign_id: str,
        target_id: str,
    ) -> NeuroCommentChannelStats:
        stats = (
            session.query(NeuroCommentChannelStats)
            .filter(
                NeuroCommentChannelStats.campaign_id == campaign_id,
                NeuroCommentChannelStats.target_id == target_id,
            )
            .one_or_none()
        )
        if stats is None:
            stats = NeuroCommentChannelStats(
                id=new_id(), campaign_id=campaign_id, target_id=target_id
            )
            session.add(stats)
        return stats

    def _account_stats(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
    ) -> NeuroCommentAccountStats:
        stats = (
            session.query(NeuroCommentAccountStats)
            .filter(
                NeuroCommentAccountStats.campaign_id == campaign_id,
                NeuroCommentAccountStats.account_id == account_id,
            )
            .one_or_none()
        )
        if stats is None:
            stats = NeuroCommentAccountStats(
                id=new_id(), campaign_id=campaign_id, account_id=account_id
            )
            session.add(stats)
        return stats
