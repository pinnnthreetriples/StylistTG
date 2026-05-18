from __future__ import annotations

from dataclasses import dataclass

from app.models import NeuroCommentCampaign, NeuroCommentCampaignAccount, NeuroCommentTarget
from app.services.neuro_commenting.enums import NeuroCampaignAccountStatus


@dataclass(frozen=True)
class AccountSelectionResult:
    account: NeuroCommentCampaignAccount | None
    reason: str | None = None


class AccountSelector:
    def select_account(
        self,
        campaign: NeuroCommentCampaign,
        accounts: list[NeuroCommentCampaignAccount],
        target: NeuroCommentTarget | None,
    ) -> AccountSelectionResult:
        for account in accounts:
            if account.status == NeuroCampaignAccountStatus.ACTIVE.value:
                return AccountSelectionResult(account=account)
        return AccountSelectionResult(account=None, reason="no_active_account")
