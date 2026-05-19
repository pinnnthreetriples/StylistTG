from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import NeuroCommentTarget, new_id
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.enums import NeuroTargetStatus
from app.services.neuro_commenting import repository


BulkSkipReason = Literal["duplicate", "blacklisted_workspace", "invalid_ref", "limit_exceeded"]


@dataclass(frozen=True)
class BulkTargetSkip:
    channel_ref: str
    reason: BulkSkipReason


@dataclass(frozen=True)
class BulkTargetResult:
    created: list[NeuroCommentTarget]
    skipped: list[BulkTargetSkip]
    requested: int


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

    def bulk_add_targets(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        items: list[dict[str, Any]],
        max_items: int = 200,
    ) -> BulkTargetResult:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        requested = len(items)
        created: list[NeuroCommentTarget] = []
        skipped: list[BulkTargetSkip] = []
        seen_in_batch: set[str] = set()
        existing_refs: set[str] = {
            target.channel_ref
            for target in (
                session.query(NeuroCommentTarget)
                .filter(NeuroCommentTarget.campaign_id == campaign.id)
                .all()
            )
        }
        rules_service = ChannelRulesService(self._analytics)

        for index, payload in enumerate(items):
            raw_ref = str(payload.get("channel_ref") or "").strip()
            if index >= max_items:
                skipped.append(BulkTargetSkip(channel_ref=raw_ref, reason="limit_exceeded"))
                continue
            if not raw_ref:
                skipped.append(BulkTargetSkip(channel_ref=raw_ref, reason="invalid_ref"))
                continue
            if raw_ref in seen_in_batch or raw_ref in existing_refs:
                skipped.append(BulkTargetSkip(channel_ref=raw_ref, reason="duplicate"))
                continue
            rule = rules_service.find_rule(
                session, workspace_id=workspace_id, target_ref=raw_ref
            )
            if rule is not None and rule.rule_type == "blacklist":
                skipped.append(BulkTargetSkip(channel_ref=raw_ref, reason="blacklisted_workspace"))
                continue
            target = NeuroCommentTarget(
                id=new_id(),
                campaign_id=campaign.id,
                channel_ref=raw_ref,
                channel_id=payload.get("channel_id"),
                discussion_chat_id=payload.get("discussion_chat_id"),
                title=payload.get("title"),
                username=payload.get("username"),
                status=NeuroTargetStatus.ACTIVE.value,
                source_type=payload.get("source_type", "channel"),
                activity_level=payload.get("activity_level"),
                keywords=repository.normalize_keywords(payload.get("keywords")),
                exclude_keywords=repository.normalize_keywords(
                    payload.get("exclude_keywords")
                ),
            )
            session.add(target)
            session.flush()
            seen_in_batch.add(raw_ref)
            existing_refs.add(raw_ref)
            created.append(target)
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                target_id=target.id,
                event_type="target_added",
                message="target channel added via bulk import",
                data={"actor_user_id": actor_user_id, "bulk_import": True},
            )
        return BulkTargetResult(created=created, skipped=skipped, requested=requested)

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
