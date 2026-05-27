from __future__ import annotations

from dataclasses import dataclass
import re

from app.modules.neuro_commenting.enums import (
    NeuroCampaignAccountStatus,
    NeuroCampaignStatus,
    NeuroSafetyStatus,
    NeuroTargetStatus,
)

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


@dataclass(frozen=True)
class CampaignSafetySnapshot:
    status: str


@dataclass(frozen=True)
class TargetSafetySnapshot:
    status: str


@dataclass(frozen=True)
class AccountSafetySnapshot:
    status: str


class SafetyPolicy:
    max_length = 120

    def check(
        self,
        *,
        text: str,
        campaign: CampaignSafetySnapshot,
        target: TargetSafetySnapshot | None = None,
        account: AccountSafetySnapshot | None = None,
        previous_texts: list[str] | None = None,
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
        if account is not None and account.status != NeuroCampaignAccountStatus.ACTIVE.value:
            return SafetyDecision(NeuroSafetyStatus.BLOCKED, "account_not_active")
        return SafetyDecision(NeuroSafetyStatus.PASSED)


__all__ = [
    "AccountSafetySnapshot",
    "CampaignSafetySnapshot",
    "SafetyDecision",
    "SafetyPolicy",
    "TargetSafetySnapshot",
]
