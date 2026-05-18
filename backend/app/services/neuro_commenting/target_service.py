from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import NeuroCommentTarget, new_id
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import NeuroTargetStatus
from app.services.neuro_commenting import repository


class TargetService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def add_target(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        payload: dict[str, Any],
    ) -> NeuroCommentTarget:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        channel_ref = str(payload.get("channel_ref") or "").strip()
        if not channel_ref:
            raise ValueError("channel_ref is required")
        target = NeuroCommentTarget(
            id=new_id(),
            campaign_id=campaign.id,
            channel_ref=channel_ref,
            channel_id=payload.get("channel_id"),
            discussion_chat_id=payload.get("discussion_chat_id"),
            title=payload.get("title"),
            username=payload.get("username"),
            status=NeuroTargetStatus.ACTIVE.value,
            source_type=payload.get("source_type", "channel"),
            activity_level=payload.get("activity_level"),
            keywords=repository.normalize_keywords(payload.get("keywords")),
            exclude_keywords=repository.normalize_keywords(payload.get("exclude_keywords")),
        )
        session.add(target)
        session.flush()
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            event_type="target_added",
            message="target channel added to neuro commenting campaign",
            data={"actor_user_id": actor_user_id},
        )
        return target

    def remove_target(
        self,
        session: Session,
        *,
        campaign_id: str,
        target_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> None:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        target = repository.require_target(session, target_id=target_id, campaign_id=campaign.id)
        session.delete(target)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target_id,
            event_type="target_removed",
            message="target channel removed from neuro commenting campaign",
            data={"actor_user_id": actor_user_id},
        )
