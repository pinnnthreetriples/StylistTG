from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.models import NeuroCommentCampaign, new_id
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import (
    NeuroApprovalMode,
    NeuroCampaignMode,
    NeuroCampaignStatus,
    NeuroEventLevel,
    NeuroRotationStrategy,
    NeuroSendMode,
    NeuroSendStrategy,
    NeuroWorkMode,
)
from app.services.neuro_commenting import repository

_MUTABLE_FIELDS = {
    "name",
    "description",
    "mode",
    "work_mode",
    "approval_mode",
    "send_mode",
    "send_strategy",
    "rotation_strategy",
    "language_mode",
    "prompt_template",
    "system_prompt",
    "negative_prompt",
    "max_comments_total",
    "max_comments_per_hour",
    "max_comments_per_day",
    "delay_min_seconds",
    "delay_max_seconds",
    "rotate_after_comments",
    "quiet_hours_start",
    "quiet_hours_end",
    "timezone",
    "dry_run",
    "auto_send_enabled",
    "safety_enabled",
}


class CampaignService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def create_campaign(
        self,
        session: Session,
        *,
        workspace_id: str,
        actor_user_id: str | None,
        payload: dict[str, Any],
    ) -> NeuroCommentCampaign:
        self._validate_payload(payload)
        payload["auto_send_enabled"] = False
        payload["dry_run"] = (
            True
            if payload.get("send_mode") == NeuroSendMode.DRY_RUN.value
            else payload.get("dry_run", True)
        )
        campaign = NeuroCommentCampaign(
            id=new_id(),
            workspace_id=workspace_id,
            name=str(payload["name"]),
            description=payload.get("description"),
            mode=payload.get("mode", NeuroCampaignMode.ALL_POSTS.value),
            work_mode=payload.get("work_mode", NeuroWorkMode.MANUAL.value),
            approval_mode=payload.get("approval_mode", NeuroApprovalMode.MANUAL_REQUIRED.value),
            send_mode=payload.get("send_mode", NeuroSendMode.DRY_RUN.value),
            send_strategy=payload.get("send_strategy", NeuroSendStrategy.COMMENT.value),
            rotation_strategy=payload.get(
                "rotation_strategy", NeuroRotationStrategy.ROUND_ROBIN.value
            ),
            language_mode=payload.get("language_mode", "auto"),
            prompt_template=payload.get("prompt_template"),
            system_prompt=payload.get("system_prompt"),
            negative_prompt=payload.get("negative_prompt"),
            max_comments_total=payload.get("max_comments_total"),
            max_comments_per_hour=payload.get("max_comments_per_hour"),
            max_comments_per_day=payload.get("max_comments_per_day"),
            delay_min_seconds=payload.get("delay_min_seconds", 60),
            delay_max_seconds=payload.get("delay_max_seconds", 300),
            rotate_after_comments=payload.get("rotate_after_comments"),
            quiet_hours_start=payload.get("quiet_hours_start"),
            quiet_hours_end=payload.get("quiet_hours_end"),
            timezone=payload.get("timezone"),
            dry_run=bool(payload.get("dry_run", True)),
            auto_send_enabled=False,
            safety_enabled=bool(payload.get("safety_enabled", True)),
        )
        session.add(campaign)
        session.flush()
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            event_type="campaign_created",
            message="neuro commenting campaign created",
            account_id=None,
            data={"actor_user_id": actor_user_id},
        )
        return campaign

    def update_campaign(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        payload: dict[str, Any],
    ) -> NeuroCommentCampaign:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        self._validate_payload(payload, partial=True)
        if payload.get("auto_send_enabled") is True:
            raise ValueError("auto-send is disabled in foundation skeleton")
        if "status" in payload:
            raise ValueError("use lifecycle endpoints to change campaign status")
        for field, value in payload.items():
            if field in _MUTABLE_FIELDS:
                setattr(campaign, field, value)
        campaign.auto_send_enabled = False
        campaign.updated_at = datetime.now(UTC)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            event_type="campaign_updated",
            message="neuro commenting campaign updated",
            data={"actor_user_id": actor_user_id, "fields": sorted(payload.keys())},
        )
        return campaign

    def start_campaign(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> NeuroCommentCampaign:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        if campaign.status not in {
            NeuroCampaignStatus.DRAFT.value,
            NeuroCampaignStatus.READY.value,
            NeuroCampaignStatus.PAUSED.value,
            NeuroCampaignStatus.STOPPED.value,
        }:
            raise ValueError("campaign status cannot be started")
        campaign.status = NeuroCampaignStatus.RUNNING.value
        campaign.started_at = datetime.now(UTC)
        campaign.stopped_at = None
        campaign.auto_send_enabled = False
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            event_type="campaign_started",
            message="neuro commenting campaign started in safe manual mode",
            data={"actor_user_id": actor_user_id},
        )
        return campaign

    def pause_campaign(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> NeuroCommentCampaign:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        if campaign.status != NeuroCampaignStatus.RUNNING.value:
            raise ValueError("only running campaign can be paused")
        campaign.status = NeuroCampaignStatus.PAUSED.value
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            event_type="campaign_paused",
            message="neuro commenting campaign paused",
            data={"actor_user_id": actor_user_id},
        )
        return campaign

    def stop_campaign(
        self,
        session: Session,
        *,
        campaign_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> NeuroCommentCampaign:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        if campaign.status in {
            NeuroCampaignStatus.ARCHIVED.value,
            NeuroCampaignStatus.COMPLETED.value,
        }:
            raise ValueError("campaign status cannot be stopped")
        campaign.status = NeuroCampaignStatus.STOPPED.value
        campaign.stopped_at = datetime.now(UTC)
        campaign.auto_send_enabled = False
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            event_type="campaign_stopped",
            message="neuro commenting campaign stopped",
            event_level=NeuroEventLevel.INFO,
            data={"actor_user_id": actor_user_id},
        )
        return campaign

    def _validate_payload(self, payload: dict[str, Any], *, partial: bool = False) -> None:
        if not partial and not payload.get("name"):
            raise ValueError("name is required")
        self._validate_enum(payload, "mode", NeuroCampaignMode)
        self._validate_enum(payload, "work_mode", NeuroWorkMode)
        self._validate_enum(payload, "approval_mode", NeuroApprovalMode)
        self._validate_enum(payload, "send_mode", NeuroSendMode)
        self._validate_enum(payload, "send_strategy", NeuroSendStrategy)
        self._validate_enum(payload, "rotation_strategy", NeuroRotationStrategy)
        if payload.get("send_mode") == NeuroSendMode.AUTO.value:
            raise ValueError("auto send mode is disabled in foundation skeleton")
        if (
            payload.get("send_strategy") != NeuroSendStrategy.COMMENT.value
            and payload.get("send_strategy") is not None
        ):
            raise ValueError("advanced send strategies are not enabled in foundation skeleton")
        if (
            payload.get("delay_max_seconds") is not None
            and payload.get("delay_min_seconds") is not None
        ):
            if int(payload["delay_max_seconds"]) < int(payload["delay_min_seconds"]):
                raise ValueError("delay_max_seconds must be >= delay_min_seconds")

    def _validate_enum(self, payload: dict[str, Any], field: str, enum_type: type[StrEnum]) -> None:
        value = payload.get(field)
        if value is None:
            return
        if value not in {item.value for item in enum_type}:
            raise ValueError(f"invalid {field}")
