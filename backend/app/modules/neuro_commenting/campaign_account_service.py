from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import NeuroCommentCampaignAccount, new_id
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import NeuroCampaignAccountStatus
from app.modules.neuro_commenting import repository


class CampaignAccountService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def add_account(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        rotation_weight: int = 1,
        rotation_order: int = 0,
    ) -> NeuroCommentCampaignAccount:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        account = repository.get_account_for_workspace(
            session, account_id=account_id, workspace_id=workspace_id
        )
        if account is None:
            raise ValueError("account not found")
        existing = repository.get_campaign_account(
            session, campaign_id=campaign.id, account_id=account_id
        )
        if existing is not None:
            return existing
        campaign_account = NeuroCommentCampaignAccount(
            id=new_id(),
            campaign_id=campaign.id,
            account_id=account_id,
            status=NeuroCampaignAccountStatus.ACTIVE.value,
            rotation_weight=rotation_weight,
            rotation_order=rotation_order,
        )
        session.add(campaign_account)
        session.flush()
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            account_id=account_id,
            event_type="campaign_account_added",
            message="account added to neuro commenting campaign",
            data={"actor_user_id": actor_user_id},
        )
        return campaign_account

    def remove_account(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> None:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        campaign_account = repository.get_campaign_account(
            session, campaign_id=campaign.id, account_id=account_id
        )
        if campaign_account is None:
            raise ValueError("campaign account not found")
        session.delete(campaign_account)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            account_id=account_id,
            event_type="campaign_account_removed",
            message="account removed from neuro commenting campaign",
            data={"actor_user_id": actor_user_id},
        )
