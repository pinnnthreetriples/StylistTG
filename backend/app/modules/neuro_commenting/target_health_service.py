from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentCampaign,
    NeuroCommentChannelRule,
    NeuroCommentTarget,
    new_id,
)
from app.modules.neuro_commenting.analytics_service import AnalyticsService


class TargetHealthService:
    _failure_deltas = {
        "SEND_FAILED": -0.10,
        "FLOOD_WAIT": -0.25,
        "COMMENTS_DISABLED": -0.40,
        "PERMISSION_DENIED": -0.30,
        "DELETED_COMMENT": -0.20,
        "NO_DISCUSSION": -0.30,
    }

    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def record_target_success(self, session: Session, *, workspace_id: str, target_id: str) -> None:
        target = self._target(session, workspace_id=workspace_id, target_id=target_id)
        target.success_count += 1
        target.health_score = self._clamp(target.health_score + 0.05)
        self._event(session, workspace_id, target, "target_health_updated")

    def record_target_failure(
        self, session: Session, *, workspace_id: str, target_id: str, error_code: str
    ) -> None:
        target = self._target(session, workspace_id=workspace_id, target_id=target_id)
        target.fail_count += 1
        target.health_score = self._clamp(
            target.health_score + self._failure_deltas.get(error_code, -0.10)
        )
        self._event(session, workspace_id, target, "target_health_updated")

    def record_target_flood_wait(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> None:
        target = self._target(session, workspace_id=workspace_id, target_id=target_id)
        target.fail_count += 1
        target.flood_wait_count += 1
        target.health_score = self._clamp(target.health_score - 0.25)
        self._event(session, workspace_id, target, "target_health_updated")

    def record_target_no_discussion(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> None:
        self.record_target_failure(
            session, workspace_id=workspace_id, target_id=target_id, error_code="NO_DISCUSSION"
        )

    def record_deleted_comment(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> None:
        target = self._target(session, workspace_id=workspace_id, target_id=target_id)
        target.deleted_comment_count += 1
        target.health_score = self._clamp(target.health_score - 0.20)
        self._event(session, workspace_id, target, "target_health_updated")

    def suggest_rules_for_target(
        self, session: Session, *, workspace_id: str, target_id: str
    ) -> None:
        target = self._target(session, workspace_id=workspace_id, target_id=target_id)
        if target.health_score <= 0.25 and target.fail_count >= 3:
            self._suggest(session, workspace_id, target, "auto_blacklist_suggested")
        if (
            target.health_score >= 0.85
            and target.success_count >= 5
            and target.flood_wait_count == 0
        ):
            self._suggest(session, workspace_id, target, "auto_whitelist_suggested")

    def _suggest(
        self,
        session: Session,
        workspace_id: str,
        target: NeuroCommentTarget,
        rule_type: str,
    ) -> None:
        exists = (
            session.query(NeuroCommentChannelRule)
            .filter_by(
                workspace_id=workspace_id,
                target_ref=target.channel_ref,
                rule_type=rule_type,
            )
            .one_or_none()
        )
        if exists is not None:
            return
        session.add(
            NeuroCommentChannelRule(
                id=new_id(),
                workspace_id=workspace_id,
                target_ref=target.channel_ref,
                rule_type=rule_type,
                reason="target health threshold reached",
            )
        )
        self._event(session, workspace_id, target, "channel_rule_created")

    def _target(self, session: Session, *, workspace_id: str, target_id: str) -> NeuroCommentTarget:
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

    def _event(
        self, session: Session, workspace_id: str, target: NeuroCommentTarget, event_type: str
    ) -> None:
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=target.campaign_id,
            target_id=target.id,
            event_type=event_type,
            message="neuro commenting target health changed",
            data={"health_score": target.health_score},
        )

    def _clamp(self, value: float) -> float:
        return round(min(1.0, max(0.0, value)), 4)
