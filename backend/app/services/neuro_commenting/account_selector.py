from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from random import Random
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountState,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentTarget,
    utc_now,
)
from app.services.neuro_commenting.enums import (
    NeuroCampaignAccountStatus,
    NeuroRotationStrategy,
)
from app.services.neuro_commenting.rate_limiter import RateLimitScope
from app.services.neuro_commenting.rules_policy import ChannelRulesPolicy

_HARD_ERROR_CODES = {"AUTH_FAILED", "SESSION_REVOKED", "PHONE_BANNED", "ACCOUNT_BANNED"}
_READY_ACCOUNT_STATES = {AccountState.AUTHORIZED_READY.value, AccountState.EXECUTION_USABLE.value}
_READY_RUNTIME_HEALTH = {"ready", "usable"}
_MIN_AWARE = datetime.min.replace(tzinfo=UTC)


class AccountReadinessProvider(Protocol):
    def is_ready(self, account_id: str) -> bool: ...


class DefaultAccountReadinessProvider:
    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def is_ready(self, account_id: str) -> bool:
        if self._session is None:
            return False
        account = self._session.get(Account, account_id)
        if account is None or account.account_state not in _READY_ACCOUNT_STATES:
            return False
        runtime = account.runtime_state
        return bool(
            runtime and runtime.session_present and runtime.runtime_health in _READY_RUNTIME_HEALTH
        )


@dataclass(frozen=True)
class AccountSkipReason:
    account_id: str
    reason: str


@dataclass(frozen=True)
class AccountSelectionResult:
    account: NeuroCommentCampaignAccount | None
    reason: str | None = None
    considered_count: int = 0
    skipped: list[AccountSkipReason] = field(default_factory=lambda: [])


class AccountSelector:
    def __init__(
        self,
        *,
        session: Session | None = None,
        readiness_provider: AccountReadinessProvider | None = None,
        limiter: Any | None = None,
        rng: Random | None = None,
    ) -> None:
        self._session = session
        self._readiness_provider = readiness_provider or DefaultAccountReadinessProvider(session)
        self._limiter = limiter
        self._rng = rng or Random()

    def select_account(
        self,
        campaign: NeuroCommentCampaign,
        accounts: list[NeuroCommentCampaignAccount],
        target: NeuroCommentTarget | None,
    ) -> AccountSelectionResult:
        now = utc_now()
        eligible: list[NeuroCommentCampaignAccount] = []
        skipped: list[AccountSkipReason] = []
        for account in accounts:
            reason = self._skip_reason(campaign, account, now)
            if reason is None and not self._readiness_provider.is_ready(account.account_id):
                reason = "runtime_not_ready"
            if reason is None and target is not None and self._is_target_blocked(campaign, target):
                reason = "blacklisted_for_target"
            if reason is None and self._is_rate_limited(campaign, account, target):
                reason = "rate_limited"
            if reason is not None:
                skipped.append(AccountSkipReason(account_id=account.account_id, reason=reason))
                continue
            eligible.append(account)
        if not eligible:
            return AccountSelectionResult(
                account=None,
                reason="no_eligible_account",
                considered_count=len(accounts),
                skipped=skipped,
            )
        selected = self._select_by_strategy(campaign.rotation_strategy, eligible)
        return AccountSelectionResult(
            account=selected,
            considered_count=len(accounts),
            skipped=skipped,
        )

    def _skip_reason(
        self,
        campaign: NeuroCommentCampaign,
        account: NeuroCommentCampaignAccount,
        now: datetime,
    ) -> str | None:
        if account.status != NeuroCampaignAccountStatus.ACTIVE.value:
            return "inactive"
        if self._session is not None:
            persisted_account = self._session.get(Account, account.account_id)
            if persisted_account is None or persisted_account.workspace_id != campaign.workspace_id:
                return "workspace_mismatch"
        if account.cooldown_until is not None and account.cooldown_until > now:
            return "cooldown"
        if account.last_error_code in _HARD_ERROR_CODES:
            return "recent_hard_error"
        return None

    def _is_target_blocked(
        self, campaign: NeuroCommentCampaign, target: NeuroCommentTarget
    ) -> bool:
        if self._session is None:
            return False
        decision = ChannelRulesPolicy().check_target_allowed(
            self._session, workspace_id=campaign.workspace_id, target=target
        )
        return not decision.allowed

    def _is_rate_limited(
        self,
        campaign: NeuroCommentCampaign,
        account: NeuroCommentCampaignAccount,
        target: NeuroCommentTarget | None,
    ) -> bool:
        if self._limiter is None:
            return False
        reservation = self._limiter.reserve(
            RateLimitScope(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                account_id=account.account_id,
                target_id=target.id if target is not None else None,
                campaign_account_id=account.id,
            )
        )
        if not reservation.allowed:
            return True
        self._limiter.rollback(reservation)
        return False

    def _select_by_strategy(
        self, strategy: str, accounts: list[NeuroCommentCampaignAccount]
    ) -> NeuroCommentCampaignAccount:
        if strategy == NeuroRotationStrategy.WEIGHTED.value:
            return self._weighted(accounts)
        if strategy == NeuroRotationStrategy.LEAST_USED.value:
            return min(
                accounts, key=lambda item: (item.comments_sent, _last_used(item.last_used_at))
            )
        if strategy == NeuroRotationStrategy.RANDOM.value:
            return self._rng.choice(accounts)
        return min(accounts, key=lambda item: (item.rotation_order, _last_used(item.last_used_at)))

    def _weighted(self, accounts: list[NeuroCommentCampaignAccount]) -> NeuroCommentCampaignAccount:
        total = sum(max(1, account.rotation_weight) for account in accounts)
        threshold = self._rng.random() * total
        cursor = 0.0
        for account in accounts:
            cursor += max(1, account.rotation_weight)
            if threshold < cursor:
                return account
        return accounts[-1]


def _last_used(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_AWARE
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
