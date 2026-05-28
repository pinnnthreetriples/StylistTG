from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountOperationCooldown, AccountState, Job, JobState, utc_now
from app.services.accounts import list_accounts

OPERATION_KEYS = (
    "profile_update",
    "username",
    "profile_photo",
    "profile_music",
    "story_post",
    "story_delete",
    "sync",
    "batch_operation",
)

RISK_ORDER = {"low": 0, "unknown": 1, "medium": 2, "high": 3, "blocked": 4}
READINESS_LEVELS = ("low", "medium", "high", "critical")


def build_risk_by_operation(
    reasons: list[dict[str, Any]],
    capabilities: dict[str, dict[str, Any]],
    cooldowns_by_operation: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    risks = {operation: _risk("low", []) for operation in OPERATION_KEYS}

    for reason in reasons:
        severity = str(reason["severity"])
        if severity == "blocked":
            for operation in OPERATION_KEYS:
                risks[operation] = _max_risk(risks[operation], "blocked", [reason])
        elif reason["code"] == "recent_flood_wait":
            for operation in OPERATION_KEYS:
                risks[operation] = _max_risk(risks[operation], "high", [reason])
        elif reason["code"] == "username_recently_rejected":
            risks["username"] = _max_risk(risks["username"], "medium", [reason])
        elif severity in {"medium", "high"}:
            for operation in (
                "profile_update",
                "username",
                "profile_photo",
                "profile_music",
                "story_post",
            ):
                risks[operation] = _max_risk(risks[operation], severity, [reason])

    capability_to_operation = {
        "profile_text": "profile_update",
        "username": "username",
        "profile_photo": "profile_photo",
        "profile_music": "profile_music",
        "story_post": "story_post",
        "story_delete": "story_delete",
        "sync": "sync",
        "auth": "batch_operation",
    }
    for capability_key, operation in capability_to_operation.items():
        capability = capabilities.get(capability_key)
        if not capability:
            continue
        if capability["state"] == "blocked":
            risks[operation] = _max_risk(risks[operation], "blocked", [])
        elif capability["state"] == "unknown":
            risks[operation] = _max_risk(risks[operation], "unknown", [])
        elif capability["state"] == "limited":
            risks[operation] = _max_risk(risks[operation], "medium", [])

    for operation, cooldowns in (cooldowns_by_operation or {}).items():
        for cooldown in cooldowns:
            level = "blocked" if cooldown["level"] == "blocked" else "medium"
            reason: dict[str, Any] = {
                "code": cooldown["reason_code"],
                "severity": level,
                "source": cooldown["source"],
                "message": "Активна пауза безопасности для операции",
                "last_seen_at": cooldown["started_at"],
            }
            risks[operation] = _max_risk(risks.get(operation, _risk("low", [])), level, [reason])

    return risks


def overall_risk_level(risk_by_operation: dict[str, dict[str, Any]]) -> str:
    return max(
        (risk["level"] for risk in risk_by_operation.values()), key=lambda level: RISK_ORDER[level]
    )


def _score_readiness_risk(
    account: Account,
    *,
    computed: datetime,
    has_cooldown: bool,
    failure_count: int,
) -> dict[str, Any]:
    score = 0
    reasons: list[dict[str, str]] = []
    runtime = account.runtime_state

    def add(points: int, code: str, severity: str, message: str) -> None:
        nonlocal score
        if code not in {reason["code"] for reason in reasons}:
            reasons.append({"code": code, "severity": severity, "message": message})
        score += points

    if account.account_state == AccountState.REAUTH_REQUIRED or bool(
        runtime and runtime.reauth_required
    ):
        add(80, "reauth_required", "critical", "Account requires reauthorization before profile jobs.")
    elif account.account_state in {
        AccountState.AWAITING_CODE,
        AccountState.AWAITING_PASSWORD,
        AccountState.AUTH_PENDING,
        AccountState.REGISTERED,
    }:
        add(45, "auth_incomplete", "warning", "Account authorization is not complete.")

    if not runtime or not runtime.session_present:
        add(65, "missing_session", "critical", "Account has no usable TDLib session snapshot.")

    runtime_health = runtime.runtime_health if runtime else "unknown"
    if runtime_health not in {"ready", "awaiting_code", "awaiting_password"}:
        severity = "critical" if runtime_health in {"broken", "closed"} else "warning"
        add(45 if severity == "critical" else 25, "runtime_unhealthy", severity, "Account runtime is not ready.")

    if account.account_state in {
        AccountState.RUNTIME_BROKEN,
        AccountState.DISABLED,
        AccountState.MANUAL_INTERVENTION_NEEDED,
    }:
        add(45, "account_locked", "critical", "Account state blocks automated work.")
    elif account.account_state not in {
        AccountState.EXECUTION_USABLE,
        AccountState.AUTHORIZED_READY,
        AccountState.REAUTH_REQUIRED,
    }:
        add(25, "unknown_state", "warning", "Account state needs operator review.")

    proxy = account.proxy
    if proxy and proxy.status in {"failed", "error"}:
        add(25, "proxy_problem", "warning", "Proxy health check failed.")
    if proxy and proxy.tdlib_last_error_code:
        add(25, "proxy_problem", "warning", "TDLib proxy verification failed.")

    if has_cooldown:
        add(35, "cooldown_active", "warning", "Account has active operation cooldowns.")

    if failure_count >= 2:
        add(25, "recent_job_failures", "warning", "Recent jobs failed repeatedly.")

    if account.profile_state is None and account.account_state in {
        AccountState.EXECUTION_USABLE,
        AccountState.AUTHORIZED_READY,
    }:
        add(10, "profile_not_synced", "info", "Profile snapshot has not been synced yet.")

    score = min(max(score, 0), 100)
    if not reasons:
        reasons.append({"code": "ready", "severity": "info", "message": "Account is ready based on stored app signals."})
    level = _readiness_level(score)
    return {
        "account_id": account.id,
        "score": score,
        "level": level,
        "reasons": reasons,
        "recommended_action": _recommended_action(level, reasons),
        "computed_at": computed,
    }


def build_account_readiness_risk(
    session: Session, account: Account, *, computed_at: datetime | None = None
) -> dict[str, Any]:
    computed = computed_at or utc_now()
    return _score_readiness_risk(
        account,
        computed=computed,
        has_cooldown=_has_active_cooldowns(session, account.id, computed),
        failure_count=_count_recent_job_failures(session, account.id),
    )


def build_account_readiness_risk_summary(session: Session, *, workspace_id: str) -> dict[str, Any]:
    computed_at = utc_now()
    accounts = list_accounts(session, workspace_id=workspace_id)
    if not accounts:
        return _empty_risk_summary(computed_at)
    account_ids = [a.id for a in accounts]
    cooldown_flags = _batch_has_active_cooldowns(session, account_ids, computed_at)
    failure_counts = _batch_count_recent_job_failures(session, account_ids)
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


def _risk(level: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
    return {"level": level, "reasons": reasons}


def _max_risk(current: dict[str, Any], level: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
    if RISK_ORDER[level] > RISK_ORDER[current["level"]]:
        return _risk(level, reasons)
    if RISK_ORDER[level] == RISK_ORDER[current["level"]] and reasons:
        return {"level": current["level"], "reasons": [*current["reasons"], *reasons]}
    return current


def _has_active_cooldowns(session: Session, account_id: str, now: datetime) -> bool:
    row = session.execute(
        select(AccountOperationCooldown.id)
        .where(AccountOperationCooldown.account_id == account_id)
        .where(AccountOperationCooldown.retry_after_at > now)
        .limit(1)
    ).first()
    return row is not None


def _count_recent_job_failures(session: Session, account_id: str) -> int:
    result = session.execute(
        select(func.count())
        .select_from(Job)
        .where(Job.account_id == account_id)
        .where(Job.job_state.in_([JobState.FAILED, JobState.MANUAL_INTERVENTION_NEEDED]))
    ).scalar()
    return result or 0


def _batch_has_active_cooldowns(
    session: Session,
    account_ids: list[str],
    now: datetime,
) -> dict[str, bool]:
    if not account_ids:
        return {}
    rows = (
        session.execute(
            select(AccountOperationCooldown.account_id)
            .where(AccountOperationCooldown.account_id.in_(account_ids))
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
) -> dict[str, int]:
    if not account_ids:
        return {}
    rows = session.execute(
        select(Job.account_id, func.count())
        .where(Job.account_id.in_(account_ids))
        .where(Job.job_state.in_([JobState.FAILED, JobState.MANUAL_INTERVENTION_NEEDED]))
        .group_by(Job.account_id)
    ).all()
    return {account_id: count for account_id, count in rows}
