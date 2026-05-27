from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import NeuroCommentAccountStats, NeuroCommentCampaignAccount, new_id, utc_now
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.enums import NeuroCampaignAccountStatus


class AccountHealthService:
    def record_account_send_success(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
        workspace_id: str,
    ) -> None:
        repository.require_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
        campaign_account = self._campaign_account(session, campaign_id, account_id)
        now = utc_now()
        campaign_account.comments_sent += 1
        campaign_account.last_used_at = now
        campaign_account.last_error_code = None
        campaign_account.status = NeuroCampaignAccountStatus.ACTIVE.value
        stats = self._stats(session, campaign_id=campaign_id, account_id=account_id)
        stats.comments_sent += 1
        stats.last_success_at = now
        stats.success_rate = self._success_rate(stats.comments_sent, stats.comments_failed)

    def record_account_send_failure(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
        workspace_id: str,
        error_code: str,
    ) -> None:
        repository.require_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
        campaign_account = self._campaign_account(session, campaign_id, account_id)
        now = utc_now()
        campaign_account.comments_failed += 1
        campaign_account.last_error_code = error_code
        stats = self._stats(session, campaign_id=campaign_id, account_id=account_id)
        stats.comments_failed += 1
        stats.last_failure_at = now
        stats.success_rate = self._success_rate(stats.comments_sent, stats.comments_failed)

    def record_account_flood_wait(
        self,
        session: Session,
        *,
        campaign_id: str,
        account_id: str,
        workspace_id: str,
        flood_wait_seconds: int,
    ) -> None:
        repository.require_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
        campaign_account = self._campaign_account(session, campaign_id, account_id)
        now = utc_now()
        campaign_account.status = NeuroCampaignAccountStatus.COOLDOWN.value
        campaign_account.cooldown_until = now + timedelta(seconds=max(1, flood_wait_seconds))
        campaign_account.last_error_code = "FLOOD_WAIT"
        stats = self._stats(session, campaign_id=campaign_id, account_id=account_id)
        stats.flood_wait_count += 1
        stats.last_failure_at = now

    def _campaign_account(
        self, session: Session, campaign_id: str, account_id: str
    ) -> NeuroCommentCampaignAccount:
        campaign_account = repository.get_campaign_account(
            session, campaign_id=campaign_id, account_id=account_id
        )
        if campaign_account is None:
            raise ValueError("campaign account not found")
        return campaign_account

    def _stats(
        self, session: Session, *, campaign_id: str, account_id: str
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
                id=new_id(),
                campaign_id=campaign_id,
                account_id=account_id,
                comments_generated=0,
                comments_sent=0,
                comments_failed=0,
                flood_wait_count=0,
                success_rate=0.0,
            )
            session.add(stats)
        return stats

    def _success_rate(self, sent: int, failed: int) -> float:
        return sent / max(sent + failed, 1)
