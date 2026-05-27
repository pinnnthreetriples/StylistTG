from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentCampaign,
    NeuroCommentChannelRule,
    NeuroCommentTarget,
    new_id,
)
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import NeuroTargetStatus


class ChannelRulesService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def list_rules(
        self,
        session: Session,
        *,
        workspace_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[NeuroCommentChannelRule], int]:
        query = session.query(NeuroCommentChannelRule).filter(
            NeuroCommentChannelRule.workspace_id == workspace_id
        )
        total = int(query.with_entities(func.count()).scalar() or 0)
        items = (
            query.order_by(NeuroCommentChannelRule.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return items, total

    def create_rule(
        self,
        session: Session,
        *,
        workspace_id: str,
        actor_user_id: str | None,
        payload: dict[str, Any],
    ) -> NeuroCommentChannelRule:
        target_ref = str(payload["target_ref"]).strip()
        existing = (
            session.query(NeuroCommentChannelRule)
            .filter(
                NeuroCommentChannelRule.workspace_id == workspace_id,
                NeuroCommentChannelRule.target_ref == target_ref,
                NeuroCommentChannelRule.rule_type == payload["rule_type"],
            )
            .order_by(NeuroCommentChannelRule.created_at.desc())
            .first()
        )
        if existing is not None:
            return existing
        rule = NeuroCommentChannelRule(
            id=new_id(),
            workspace_id=workspace_id,
            target_ref=target_ref,
            rule_type=payload["rule_type"],
            reason=payload.get("reason"),
            created_by=actor_user_id,
        )
        session.add(rule)
        session.flush()
        event_type = (
            "target_blacklisted"
            if rule.rule_type == "blacklist"
            else "target_whitelisted"
            if rule.rule_type == "whitelist"
            else "channel_rule_created"
        )
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            event_type=event_type,
            message="neuro commenting channel rule created",
            data={"rule_id": rule.id, "target_ref": rule.target_ref, "rule_type": rule.rule_type},
        )
        return rule

    def delete_rule(self, session: Session, *, workspace_id: str, rule_id: str) -> None:
        rule = self._require_rule(session, workspace_id=workspace_id, rule_id=rule_id)
        session.delete(rule)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            event_type="channel_rule_deleted",
            message="neuro commenting channel rule deleted",
            data={"rule_id": rule_id, "target_ref": rule.target_ref},
        )

    def find_rule(
        self, session: Session, *, workspace_id: str, target_ref: str
    ) -> NeuroCommentChannelRule | None:
        return (
            session.query(NeuroCommentChannelRule)
            .filter(
                NeuroCommentChannelRule.workspace_id == workspace_id,
                NeuroCommentChannelRule.target_ref == target_ref,
                NeuroCommentChannelRule.rule_type.in_(["blacklist", "whitelist"]),
            )
            .order_by(NeuroCommentChannelRule.created_at.desc())
            .first()
        )

    def target_rule_status(self, session: Session, *, workspace_id: str, target_ref: str) -> str:
        rule = self.find_rule(session, workspace_id=workspace_id, target_ref=target_ref)
        return rule.rule_type if rule is not None else "none"

    def require_target(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> NeuroCommentTarget:
        return self._require_target(session, workspace_id=workspace_id, target_id=target_id)

    def pause_target(
        self,
        session: Session,
        *,
        target_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> NeuroCommentTarget:
        target = self._require_target(session, workspace_id=workspace_id, target_id=target_id)
        target.status = NeuroTargetStatus.PAUSED.value
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=target.campaign_id,
            target_id=target.id,
            event_type="target_paused",
            message="neuro commenting target paused",
            data={"actor_user_id": actor_user_id},
        )
        return target

    def resume_target(
        self,
        session: Session,
        *,
        target_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> NeuroCommentTarget:
        target = self._require_target(session, workspace_id=workspace_id, target_id=target_id)
        target.status = NeuroTargetStatus.ACTIVE.value
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=target.campaign_id,
            target_id=target.id,
            event_type="target_resumed",
            message="neuro commenting target resumed",
            data={"actor_user_id": actor_user_id},
        )
        return target

    def _require_rule(
        self, session: Session, *, workspace_id: str, rule_id: str
    ) -> NeuroCommentChannelRule:
        rule = (
            session.query(NeuroCommentChannelRule)
            .filter(
                NeuroCommentChannelRule.id == rule_id,
                NeuroCommentChannelRule.workspace_id == workspace_id,
            )
            .one_or_none()
        )
        if rule is None:
            raise ValueError("channel rule not found")
        return rule

    def _require_target(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> NeuroCommentTarget:
        target = (
            session.query(NeuroCommentTarget)
            .join(NeuroCommentCampaign, NeuroCommentCampaign.id == NeuroCommentTarget.campaign_id)
            .filter(
                NeuroCommentTarget.id == target_id,
                NeuroCommentCampaign.workspace_id == workspace_id,
            )
            .one_or_none()
        )
        if target is None:
            raise ValueError("target not found")
        return target
