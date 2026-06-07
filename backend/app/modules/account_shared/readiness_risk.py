from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountOperationCooldown, AccountState, Job, JobState, utc_now
from app.modules.account_shared.interfaces import list_workspace_accounts

READINESS_LEVELS = ("low", "medium", "high", "critical")


def _empty_readiness_reasons() -> list[dict[str, str]]:
    return []


@dataclass
class _ReadinessAccumulator:
    score: int = 0
    reasons: list[dict[str, str]] = field(default_factory=_empty_readiness_reasons)

    def add(self, points: int, code: str, severity: str, message: str) -> None:
        if code not in {reason["code"] for reason in self.reasons}:
            self.reasons.append({"code": code, "severity": severity, "message": message})
        self.score += points


def build_account_readiness_risk(
    session: Session, account: Account, *, computed_at: datetime | None = None
) -> dict[str, Any]:
    computed = computed_at or utc_now()
    return _score_readiness_risk(
        account,
        computed=computed,
        has_cooldown=_has_active_cooldowns(
            session, account.id, workspace_id=account.workspace_id, now=computed
        ),
        failure_count=_count_recent_job_failures(
            session, account.id, workspace_id=account.workspace_id
        ),
    )


def build_account_readiness_risk_summary(session: Session, *, workspace_id: str) -> dict[str, Any]:
    computed_at = utc_now()
    accounts = list_workspace_accounts(session, workspace_id=workspace_id)
    if not accounts:
        return _empty_risk_summary(computed_at)
    account_ids = [a.id for a in accounts]
    cooldown_flags = _batch_has_active_cooldowns(
        session, account_ids, workspace_id=workspace_id, now=computed_at
    )
    failure_counts = _batch_count_recent_job_failures(
        session, account_ids, workspace_id=workspace_id
    )
    items = [
        _build_readiness_risk_prefetched(
            session,
            account,
            computed_at=computed_at,
            has_cooldown=cooldown_flags.get(account.id, False),
            failure_count=failure_counts.get(account.id, 0),
        )
        for account in accounts
    ]
    counts = {level: 0 for level in READINESS_LEVELS}
    reauth_required = 0
    missing_session = 0
    runtime_unhealthy = 0
    proxy_problem = 0
    for item in items:
        counts[item["level"]] += 1
        codes = {reason["code"] for reason in item["reasons"]}
        reauth_required += int("reauth_required" in codes)
        missing_session += int("missing_session" in codes)
        runtime_unhealthy += int("runtime_unhealthy" in codes)
        proxy_problem += int("proxy_problem" in codes)
    return {
        "total": len(items),
        "low": counts["low"],
        "medium": counts["medium"],
        "high": counts["high"],
        "critical": counts["critical"],
        "reauth_required": reauth_required,
        "missing_session": missing_session,
        "runtime_unhealthy": runtime_unhealthy,
        "proxy_problem": proxy_problem,
        "items": items,
        "computed_at": computed_at,
    }


def _score_readiness_risk(
    account: Account,
    *,
    computed: datetime,
    has_cooldown: bool,
    failure_count: int,
) -> dict[str, Any]:
    accumulator = _ReadinessAccumulator()
    _score_auth_state(account, accumulator)
    _score_runtime_state(account, accumulator)
    _score_account_state(account, accumulator)
    _score_proxy_state(account, accumulator)
    _score_activity_state(
        account,
        accumulator,
        has_cooldown=has_cooldown,
        failure_count=failure_count,
    )

    score = min(max(accumulator.score, 0), 100)
    if not accumulator.reasons:
        accumulator.reasons.append(
            {
                "code": "ready",
                "severity": "info",
                "message": "Account is ready based on stored app signals.",
            }
        )
    level = _readiness_level(score)
    return {
        "account_id": account.id,
        "score": score,
        "level": level,
        "reasons": accumulator.reasons,
        "recommended_action": _recommended_action(level, accumulator.reasons),
        "computed_at": computed,
    }


def _score_auth_state(account: Account, accumulator: _ReadinessAccumulator) -> None:
    runtime = account.runtime_state
    if account.account_state == AccountState.REAUTH_REQUIRED or bool(
        runtime and runtime.reauth_required
    ):
        accumulator.add(
            80,
            "reauth_required",
            "critical",
            "Account requires reauthorization before profile jobs.",
        )
    elif account.account_state in {
        AccountState.AWAITING_CODE,
        AccountState.AWAITING_PASSCODE,
        AccountState.AUTH_PENDING,
        AccountState.REGISTERED,
    }:
        accumulator.add(45, "auth_incomplete", "warning", "Account authorization is not complete.")


def _score_runtime_state(account: Account, accumulator: _ReadinessAccumulator) -> None:
    runtime = account.runtime_state
    if not runtime or not runtime.session_present:
        accumulator.add(
            65, "missing_session", "critical", "Account has no usable TDLib session snapshot."
        )

    runtime_health = runtime.runtime_health if runtime else "unknown"
    if runtime_health not in {"ready", "awaiting_code", "awaiting_password"}:
        severity = "critical" if runtime_health in {"broken", "closed"} else "warning"
        accumulator.add(
            45 if severity == "critical" else 25,
            "runtime_unhealthy",
            severity,
            "Account runtime is not ready.",
        )


def _score_account_state(account: Account, accumulator: _ReadinessAccumulator) -> None:
    if account.account_state in {
        AccountState.RUNTIME_BROKEN,
        AccountState.DISABLED,
        AccountState.MANUAL_INTERVENTION_NEEDED,
    }:
        accumulator.add(45, "account_locked", "critical", "Account state blocks automated work.")
    elif account.account_state not in {
        AccountState.EXECUTION_USABLE,
        AccountState.AUTHORIZED_READY,
        AccountState.REAUTH_REQUIRED,
    }:
        accumulator.add(25, "unknown_state", "warning", "Account state needs operator review.")


def _score_proxy_state(account: Account, accumulator: _ReadinessAccumulator) -> None:
    proxy = account.proxy
    if proxy and proxy.status in {"failed", "error"}:
        accumulator.add(25, "proxy_problem", "warning", "Proxy health check failed.")
    if proxy and proxy.tdlib_last_error_code:
        accumulator.add(25, "proxy_problem", "warning", "TDLib proxy verification failed.")


def _score_activity_state(
    account: Account,
    accumulator: _ReadinessAccumulator,
    *,
    has_cooldown: bool,
    failure_count: int,
) -> None:
    if has_cooldown:
        accumulator.add(35, "cooldown_active", "warning", "Account has active operation cooldowns.")
    if failure_count >= 2:
        accumulator.add(25, "recent_job_failures", "warning", "Recent jobs failed repeatedly.")
    if account.profile_state is None and account.account_state in {
        AccountState.EXECUTION_USABLE,
        AccountState.AUTHORIZED_READY,
    }:
        accumulator.add(
            10, "profile_not_synced", "info", "Profile snapshot has not been synced yet."
        )


def _empty_risk_summary(computed_at: datetime) -> dict[str, Any]:
    return {
        "total": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
        "reauth_required": 0,
        "missing_session": 0,
        "runtime_unhealthy": 0,
        "proxy_problem": 0,
        "items": [],
        "computed_at": computed_at,
    }


def _build_readiness_risk_prefetched(
    session: Session,
    account: Account,
    *,
    computed_at: datetime,
    has_cooldown: bool,
    failure_count: int,
) -> dict[str, Any]:
    return _score_readiness_risk(
        account,
        computed=computed_at,
        has_cooldown=has_cooldown,
        failure_count=failure_count,
    )


def _readiness_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _recommended_action(level: str, reasons: list[dict[str, str]]) -> str | None:
    codes = {reason["code"] for reason in reasons}
    if "reauth_required" in codes or "auth_incomplete" in codes:
        return "Reauthorize account before running profile jobs."
    if "missing_session" in codes:
        return "Restore or recreate the account session before enabling live work."
    if "runtime_unhealthy" in codes:
        return "Refresh runtime diagnostics and review the account before running jobs."
    if "proxy_problem" in codes:
        return "Review proxy configuration before live execution."
    if "cooldown_active" in codes:
        return "Wait for the active cooldown to expire."
    if level == "low":
        return None
    return "Review account readiness before running jobs."


def _has_active_cooldowns(
    session: Session, account_id: str, *, workspace_id: str, now: datetime
) -> bool:
    row = session.execute(
        select(AccountOperationCooldown.id)
        .join(Account, Account.id == AccountOperationCooldown.account_id)
        .where(AccountOperationCooldown.account_id == account_id)
        .where(Account.workspace_id == workspace_id)
        .where(AccountOperationCooldown.retry_after_at > now)
        .limit(1)
    ).first()
    return row is not None


def _count_recent_job_failures(session: Session, account_id: str, *, workspace_id: str) -> int:
    result = session.execute(
        select(func.count())
        .select_from(Job)
        .where(Job.account_id == account_id)
        .where(Job.workspace_id == workspace_id)
        .where(Job.job_state.in_([JobState.FAILED, JobState.MANUAL_INTERVENTION_NEEDED]))
    ).scalar()
    return result or 0


def _batch_has_active_cooldowns(
    session: Session,
    account_ids: list[str],
    *,
    workspace_id: str,
    now: datetime,
) -> dict[str, bool]:
    if not account_ids:
        return {}
    rows = (
        session.execute(
            select(AccountOperationCooldown.account_id)
            .join(Account, Account.id == AccountOperationCooldown.account_id)
            .where(AccountOperationCooldown.account_id.in_(account_ids))
            .where(Account.workspace_id == workspace_id)
            .where(AccountOperationCooldown.retry_after_at > now)
            .distinct()
        )
        .scalars()
        .all()
    )
    return {account_id: True for account_id in rows}


def _batch_count_recent_job_failures(
    session: Session,
    account_ids: list[str],
    *,
    workspace_id: str,
) -> dict[str, int]:
    if not account_ids:
        return {}
    rows = session.execute(
        select(Job.account_id, func.count())
        .where(Job.account_id.in_(account_ids))
        .where(Job.workspace_id == workspace_id)
        .where(Job.job_state.in_([JobState.FAILED, JobState.MANUAL_INTERVENTION_NEEDED]))
        .group_by(Job.account_id)
    ).all()
    return {account_id: count for account_id, count in rows}


__all__ = ["build_account_readiness_risk", "build_account_readiness_risk_summary"]
