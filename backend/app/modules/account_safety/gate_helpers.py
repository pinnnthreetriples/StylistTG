from __future__ import annotations

# pyright: reportUnusedFunction=false

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.account_safety.cache import (
    NullSafetyGateCache,
    RedisSafetyGateCache,
    SafetyGateCache,
)
from app.modules.account_safety.gate_contracts import (
    SafetyGateIntent,
    SafetyGateReason,
    SafetyGateReasonCode,
    SafetyGateVerdict,
)
from app.modules.account_safety.policy import (
    get_workspace_safety_policy,
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
from app.modules.account_profile_completeness.interfaces import (
    evaluate as evaluate_profile_completeness,
)
from app.services.cross_module_load_tracker import SafetyMode as CrossModuleSafetyMode
from app.modules.account_ggr.interfaces import get_ggr_score
from app.services.redis_client import redis_from_url

CACHE_TTL_SECONDS = 60
STALE_CACHE_TTL_SECONDS = 300
COLD_CALL_BUDGET_PER_MINUTE = 1
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


def _effective_safety_mode(
    account: Account,
    policy: WorkspaceSafetyPolicy,
    now: datetime,
) -> str:
    if policy.mode != "conservative" or account.safety_grace_period_until is None:
        return policy.mode
    if _as_utc(account.safety_grace_period_until) > _as_utc(now):
        return "balanced"
    return policy.mode


def _cross_module_safety_mode(
    policy: WorkspaceSafetyPolicy,
    effective_mode: str | None = None,
) -> CrossModuleSafetyMode:
    mode = effective_mode or policy.mode
    if mode not in {"conservative", "balanced", "aggressive"}:
        raise ValueError(f"unsupported workspace safety policy mode: {mode}")
    return cast(CrossModuleSafetyMode, mode)


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


def _account_cache_state(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
) -> tuple[str, datetime | None]:
    row = session.execute(
        select(  # nosemgrep: missing-workspace-id-filter-projection - workspace_id predicate is below.
            Account.terminal_status, Account.safety_grace_period_until
        )
        .where(Account.workspace_id == workspace_id)
        .where(Account.id == account_id)
    ).one_or_none()
    if row is None:
        raise AccountSafetyGateAccountNotFound("account not found")
    return str(row[0]), row[1]


def _cache_key(
    *,
    account_id: str,
    intent: SafetyGateIntent,
    policy: WorkspaceSafetyPolicy,
    terminal_status: str,
    safety_grace_period_until: datetime | None,
) -> str:
    updated_at = policy.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    grace_key = (
        _as_utc(safety_grace_period_until).isoformat()
        if safety_grace_period_until is not None
        else "none"
    )
    return (
        f"safety:gate:{account_id}:{intent}:{updated_at.isoformat()}:{terminal_status}:{grace_key}"
    )


def _stale_cache_key(*, account_id: str, intent: SafetyGateIntent) -> str:
    return f"safety:gate:stale:{account_id}:{intent}"


def _default_cache() -> SafetyGateCache:
    try:
        return RedisSafetyGateCache.from_settings()
    except Exception:
        return NullSafetyGateCache()


def _default_redis() -> Any | None:
    try:
        return redis_from_url()
    except Exception:
        return None


def _fail_closed_verdict(*, account_id: str, intent: SafetyGateIntent) -> SafetyGateVerdict:
    return SafetyGateVerdict(
        account_id=UUID(account_id),
        intent=intent,
        eligible=False,
        severity="blocked",
        reasons=[
            _reason(
                "cross_module_overload",
                "blocked",
                "Safety gate cold-call budget exceeded.",
                {"budget": "cold_call"},
            )
        ],
        ggr_score=None,
        checked_at=utc_now(),
        cache_ttl_seconds=0,
    )


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
    return (utc_now() - _as_utc(created_at)).total_seconds() / 3600


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


def _is_status_degraded(status: AccountStatusObservation, *, threshold: int) -> bool:
    return status.consecutive_failures >= threshold or status.auto_action_taken in {
        "paused",
        "quarantine",
    }


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
