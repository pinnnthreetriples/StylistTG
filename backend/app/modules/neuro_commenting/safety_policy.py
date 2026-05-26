from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentTarget,
)
from app.modules.neuro_commenting.enums import (
    NeuroCampaignAccountStatus,
    NeuroCampaignStatus,
    NeuroSafetyStatus,
    NeuroTargetStatus,
)
from app.modules.neuro_commenting.rules_policy import ChannelRulesPolicy

_URL_PATTERN = re.compile(r"(?:https?://|www\.|t\.me/|telegram\.me/)", re.IGNORECASE)
_AD_WORDS = ("купи", "купить", "скидка", "промокод", "заработок", "подпишись")
_BLOCKED_WORDS = ("оскорбление", "ненавижу", "лох", "дурак")


@dataclass(frozen=True)
class SafetyDecision:
    status: NeuroSafetyStatus
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.status == NeuroSafetyStatus.PASSED


class SafetyPolicy:
    max_length = 120

    def check(
        self,
        *,
        text: str,
        campaign: NeuroCommentCampaign,
        target: NeuroCommentTarget | None = None,
        account: NeuroCommentCampaignAccount | None = None,
        previous_texts: list[str] | None = None,
        session: Session | None = None,
        workspace_id: str | None = None,
    ) -> SafetyDecision:
        normalized = text.strip()
        if not normalized:
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "empty_text")
        if len(normalized) > self.max_length:
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "too_long")
        if _URL_PATTERN.search(normalized):
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "links_blocked")
        lowered = normalized.lower()
        if any(word in lowered for word in _BLOCKED_WORDS):
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "blocked_words")
        if any(word in lowered for word in _AD_WORDS):
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "explicit_advertising")
        if previous_texts and lowered in {item.strip().lower() for item in previous_texts}:
            return SafetyDecision(NeuroSafetyStatus.NEEDS_REVIEW, "duplicate_text")
        if campaign.status not in {
            NeuroCampaignStatus.READY.value,
            NeuroCampaignStatus.RUNNING.value,
        }:
            return SafetyDecision(NeuroSafetyStatus.NEEDS_REVIEW, "campaign_not_running")
        if target is not None and target.status != NeuroTargetStatus.ACTIVE.value:
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "target_not_active")
        if target is not None and session is not None and workspace_id is not None:
            rule_decision = ChannelRulesPolicy().check_target_allowed(
                session, workspace_id=workspace_id, target=target
            )
            if not rule_decision.allowed:
                return SafetyDecision(NeuroSafetyStatus.BLOCKED, rule_decision.reason)
        if account is not None and account.status != NeuroCampaignAccountStatus.ACTIVE.value:
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "account_not_active")
        return SafetyDecision(NeuroSafetyStatus.PASSED)
