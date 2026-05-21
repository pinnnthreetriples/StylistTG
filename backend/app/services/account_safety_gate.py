from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.contracts.safety_gate import (
    SafetyGateIntent,
    SafetyGateReason,
    SafetyGateReasonCode,
    SafetyGateVerdict,
)
from app.models import (
    Account,
    AccountOperationCooldown,
    AccountState,
    AccountStatusObservation,
    WarmupSession,
    WarmupStatus,
    WorkspaceSafetyPolicy,
    utc_now,
)
from app.services.account_profile_completeness import evaluate as evaluate_profile_completeness
from app.services.account_quarantine import get_active_quarantine
from app.services.cross_module_load_tracker import current_load, evaluate_threshold
from app.services.cross_module_load_tracker import SafetyMode as CrossModuleSafetyMode
from app.services.ggr_calculator import calculate_ggr, get_ggr_score
from app.services.safety_gate_cache import (
    InMemorySafetyGateCache,
    NullSafetyGateCache,
    RedisSafetyGateCache,
    SafetyGateCache,
)
from app.services.workspace_safety_policy import get_workspace_safety_policy

CACHE_TTL_SECONDS = 60
_HEALTHY_PROXY_STATUSES = {"ok", "tcp_working", "tdlib_working"}
_TERMINAL_ACCOUNT_STATES = {
    AccountState.DISABLED.value,
    AccountState.MANUAL_INTERVENTION_NEEDED.value,
}
_CRITICAL_ACCOUNT_STATES = {
    *_TERMINAL_ACCOUNT_STATES,
    AccountState.RUNTIME_BROKEN.value,
    AccountState.REAUTH_REQUIRED.value,
}


class AccountSafetyGateAccountNotFound(LookupError):
    pass


class AccountSafetyGate:
    def __init__(self, *, cache: SafetyGateCache | None = None) -> None:
        self._cache = cache if cache is not None else _default_cache()

    def evaluate(
        self,
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        intent: SafetyGateIntent,
    ) -> SafetyGateVerdict:
        policy = _policy(session, workspace_id=workspace_id)
        terminal_status = _account_terminal_status(
            session, workspace_id=workspace_id, account_id=account_id
        )
        cache_key = _cache_key(
            account_id=account_id,
            intent=intent,
            policy=policy,
            terminal_status=terminal_status,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return SafetyGateVerdict.model_validate_json(cached)

        verdict = self._compute_verdict(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            intent=intent,
            policy=policy,
        )
        self._cache.set(cache_key, verdict.model_dump_json(), ttl_seconds=CACHE_TTL_SECONDS)
        return verdict

    def _compute_verdict(
        self,
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        intent: SafetyGateIntent,
        policy: WorkspaceSafetyPolicy,
    ) -> SafetyGateVerdict:
        account = _account(session, workspace_id=workspace_id, account_id=account_id)
        reasons: list[SafetyGateReason] = []
        ggr = get_ggr_score(session, account_id, workspace_id) or calculate_ggr(
            session, account, workspace_id
        )
        ggr_score = float(ggr.score)

        if intent == "commenting":
            reasons.extend(
                _commenting_reasons(session, account=account, policy=policy, ggr_score=ggr_score)
            )
        elif intent == "warmup":
            reasons.extend(_warmup_reasons(account=account, policy=policy))
        elif intent == "editing":
            reasons.extend(_editing_reasons(account=account))
        else:
            raise ValueError(f"unsupported safety gate intent: {intent}")

        if account.terminal_status != "none":
            reasons.append(_terminal_reason(account))

        quarantine = get_active_quarantine(
            session, account_id=account.id, workspace_id=account.workspace_id
        )
        if quarantine is not None:
            reasons.append(
                _reason(
                    "active_quarantine",
                    "blocked",
                    "Account has an active quarantine.",
                    {"quarantine_id": quarantine.id, "reason": quarantine.reason},
                )
            )

        status = _latest_status(session, account=account)
        if status is not None:
            if (
                status.auto_action_taken == "cooldown"
                and _as_utc(status.observed_at) + timedelta(minutes=30) > utc_now()
            ):
                reasons.append(
                    _reason(
                        "ip_change_cooldown",
                        "warning",
                        "Account is in an IP-change cooldown window.",
                        {"observed_at": status.observed_at.isoformat()},
                    )
                )
            if _is_status_degraded(status):
                reasons.append(
                    _reason(
                        "status_degraded",
                        "warning",
                        "Recent account status observations are degraded.",
                        {"consecutive_failures": status.consecutive_failures},
                    )
                )

        if intent == "commenting":
            load = current_load(session, workspace_id=account.workspace_id, account_id=account.id)
            load_verdict = evaluate_threshold(load, _cross_module_safety_mode(policy))
            if load_verdict != "ok":
                reasons.append(
                    _reason(
                        "cross_module_overload",
                        load_verdict,
                        "Account has too much cross-module activity.",
                        {"last_hour": load.last_hour, "last_24h": load.last_24h},
                    )
                )

        severity = _aggregate_severity(reasons)
        return SafetyGateVerdict(
            account_id=UUID(account.id),
            intent=intent,
            eligible=severity != "blocked",
            severity=severity,
            reasons=reasons,
            ggr_score=ggr_score,
            checked_at=utc_now(),
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )


def evaluate(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    intent: SafetyGateIntent,
    cache: SafetyGateCache | None = None,
) -> SafetyGateVerdict:
    return AccountSafetyGate(cache=cache).evaluate(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        intent=intent,
    )


def _commenting_reasons(
    session: Session,
    *,
    account: Account,
    policy: WorkspaceSafetyPolicy,
    ggr_score: float | None,
) -> list[SafetyGateReason]:
    reasons: list[SafetyGateReason] = []
    if policy.require_healthy_proxy and not _proxy_healthy(account):
        reasons.append(_proxy_reason("blocked", account))
    warmup = _latest_warmup(session, account=account)
    if policy.require_warmup_before_commenting:
        if warmup is None:
            reasons.append(_reason("no_warmup", "blocked", "Account has no warmup session."))
        elif not _warmup_complete(warmup, policy):
            reasons.append(
                _reason(
                    "warmup_incomplete",
                    "blocked",
                    "Account warmup is not complete.",
                    {"status": warmup.status, "current_day": warmup.current_day},
                )
            )
    if _age_hours(account) < policy.min_account_age_hours:
        reasons.append(
            _reason(
                "age_too_low",
                "blocked",
                "Account age is below the workspace safety policy minimum.",
                {"min_account_age_hours": policy.min_account_age_hours},
            )
        )
    if ggr_score is not None and ggr_score < 4.0:
        reasons.append(_reason("ggr_too_low", "blocked", "Account GGR score is too low."))
    fraud_score = _fraud_score(session, account)
    if fraud_score >= 0.7:
        reasons.append(
            _reason(
                "fraud_score_high",
                "blocked",
                "Account fraud score is too high.",
                {"fraud_score": fraud_score},
            )
        )
    if _recent_flood_waits(session, account=account) >= policy.auto_pause_on_flood_wait_count:
        reasons.append(
            _reason(
                "flood_wait_streak",
                "blocked",
                "Recent flood-wait count reached the workspace safety threshold.",
                {"threshold": policy.auto_pause_on_flood_wait_count},
            )
        )
    profile = evaluate_profile_completeness(
        session, workspace_id=account.workspace_id, account_id=account.id
    )
    if profile.score < 0.8:
        reasons.append(
            _reason(
                "profile_incomplete",
                "blocked",
                "Account profile completeness is below the commenting threshold.",
                {"score": profile.score},
            )
        )
    if account.terminal_status == "none" and account.account_state in _TERMINAL_ACCOUNT_STATES:
        reasons.append(_terminal_reason(account))
    return reasons


def _warmup_reasons(account: Account, policy: WorkspaceSafetyPolicy) -> list[SafetyGateReason]:
    reasons: list[SafetyGateReason] = []
    if policy.require_healthy_proxy and not _proxy_healthy(account):
        reasons.append(_proxy_reason("blocked", account))
    if account.terminal_status == "none" and account.account_state in _TERMINAL_ACCOUNT_STATES:
        reasons.append(_terminal_reason(account))
    # TODO Phase 2.5 Task 27: replace cache-only path with Lua reserve+verdict for sender preflight atomicity.
    # Warmup isolation conflict check will be wired when a dedicated conflict service exists.
    return reasons


def _editing_reasons(account: Account) -> list[SafetyGateReason]:
    reasons: list[SafetyGateReason] = []
    if not _proxy_healthy(account):
        reasons.append(_proxy_reason("warning", account))
    if account.terminal_status == "none" and account.account_state in _CRITICAL_ACCOUNT_STATES:
        reasons.append(_terminal_reason(account))
    return reasons


def _policy(session: Session, *, workspace_id: str) -> WorkspaceSafetyPolicy:
    policy = get_workspace_safety_policy(session, workspace_id=workspace_id, create_if_missing=True)
    if policy is None:
        raise RuntimeError("workspace safety policy was not created")
    return policy


def _cross_module_safety_mode(policy: WorkspaceSafetyPolicy) -> CrossModuleSafetyMode:
    if policy.mode not in {"conservative", "balanced", "aggressive"}:
        raise ValueError(f"unsupported workspace safety policy mode: {policy.mode}")
    return cast(CrossModuleSafetyMode, policy.mode)


def _account(session: Session, *, workspace_id: str, account_id: str) -> Account:
    account = (
        session.execute(
            select(Account)
            .where(Account.workspace_id == workspace_id)
            .where(Account.id == account_id)
            .options(joinedload(Account.proxy), joinedload(Account.runtime_state))
        )
        .scalars()
        .unique()
        .first()
    )
    if account is None:
        raise AccountSafetyGateAccountNotFound("account not found")
    return account


def _account_terminal_status(session: Session, *, workspace_id: str, account_id: str) -> str:
    terminal_status = session.scalar(
        select(Account.terminal_status)
        .where(Account.workspace_id == workspace_id)
        .where(Account.id == account_id)
    )
    if terminal_status is None:
        raise AccountSafetyGateAccountNotFound("account not found")
    return str(terminal_status)


def _cache_key(
    *,
    account_id: str,
    intent: SafetyGateIntent,
    policy: WorkspaceSafetyPolicy,
    terminal_status: str,
) -> str:
    updated_at = policy.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return f"safety:gate:{account_id}:{intent}:{updated_at.isoformat()}:{terminal_status}"


def _default_cache() -> SafetyGateCache:
    try:
        return RedisSafetyGateCache.from_settings()
    except Exception:
        return NullSafetyGateCache()


def _reason(
    code: SafetyGateReasonCode,
    severity: Literal["warning", "blocked"],
    message: str,
    metadata: dict[str, object] | None = None,
) -> SafetyGateReason:
    return SafetyGateReason(
        code=code,
        severity=severity,
        message=message,
        metadata=dict(metadata or {}),
    )


def _proxy_reason(severity: Literal["warning", "blocked"], account: Account) -> SafetyGateReason:
    return _reason(
        "proxy_unhealthy",
        severity,
        "Account proxy is not healthy.",
        {"status": account.proxy.status if account.proxy else None},
    )


def _terminal_reason(account: Account) -> SafetyGateReason:
    metadata_key = "status" if account.terminal_status != "none" else "account_state"
    metadata_value = (
        account.terminal_status if account.terminal_status != "none" else account.account_state
    )
    return _reason(
        "terminal_status",
        "blocked",
        "Account status blocks safety-gated actions.",
        {metadata_key: metadata_value},
    )


def _proxy_healthy(account: Account) -> bool:
    return bool(account.proxy and account.proxy.status in _HEALTHY_PROXY_STATUSES)


def _latest_warmup(session: Session, *, account: Account) -> WarmupSession | None:
    return session.execute(
        select(WarmupSession)
        .where(WarmupSession.workspace_id == account.workspace_id)
        .where(WarmupSession.account_id == account.id)
        .order_by(WarmupSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _warmup_complete(warmup: WarmupSession, policy: WorkspaceSafetyPolicy) -> bool:
    return (
        warmup.status == WarmupStatus.COMPLETED.value
        and warmup.current_day >= policy.min_warmup_days
    )


def _age_hours(account: Account) -> float:
    created_at = account.created_at
    return (datetime.now(UTC) - _as_utc(created_at)).total_seconds() / 3600


def _fraud_score(session: Session, account: Account) -> float:
    ggr = get_ggr_score(session, account.id, account.workspace_id)
    if ggr is None:
        return 0.0
    value = (ggr.breakdown_json or {}).get("fraud_score", 0.0)
    return float(value or 0.0)


def _recent_flood_waits(session: Session, *, account: Account) -> int:
    since = utc_now() - timedelta(hours=24)
    return int(
        session.scalar(
            select(func.count(AccountOperationCooldown.account_id))
            .join(Account, Account.id == AccountOperationCooldown.account_id)
            .where(Account.workspace_id == account.workspace_id)
            .where(AccountOperationCooldown.account_id == account.id)
            .where(AccountOperationCooldown.reason_code == "recent_flood_wait")
            .where(AccountOperationCooldown.started_at >= since)
        )
        or 0
    )


def _latest_status(session: Session, *, account: Account) -> AccountStatusObservation | None:
    return session.execute(
        select(AccountStatusObservation)
        .where(AccountStatusObservation.workspace_id == account.workspace_id)
        .where(AccountStatusObservation.account_id == account.id)
        .order_by(AccountStatusObservation.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _is_status_degraded(status: AccountStatusObservation) -> bool:
    return status.consecutive_failures >= 3 or status.auto_action_taken in {"paused", "quarantine"}


def _aggregate_severity(reasons: list[SafetyGateReason]) -> Literal["ok", "warning", "blocked"]:
    if any(reason.severity == "blocked" for reason in reasons):
        return "blocked"
    if any(reason.severity == "warning" for reason in reasons):
        return "warning"
    return "ok"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "AccountSafetyGate",
    "AccountSafetyGateAccountNotFound",
    "InMemorySafetyGateCache",
    "evaluate",
]
