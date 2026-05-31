from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountProxy,
    AccountValidityCheckRun,
    utc_now,
)
from app.modules.account_safety.cooldowns import (
    active_cooldowns_by_operation,
    batch_active_cooldowns_by_operation,
    batch_latest_succeeded_steps,
    batch_recent_failed_steps,
    merge_cooldowns,
    product_cooldowns_by_operation,
    product_cooldowns_from_steps,
    recent_failure_cooldowns_by_operation,
    recent_failure_cooldowns_from_steps,
)
from app.modules.account_safety.health import (
    batch_latest_failed_steps,
    batch_latest_jobs,
    collect_account_health_signals,
    collect_account_health_signals_prefetched,
)
from app.modules.account_safety.overrides import active_overrides_by_operation, batch_active_overrides_by_operation
from app.modules.account_safety.preview import (
    safety_preview_fields,
    safety_preview_fields_with_policy,
    unique_preserve_order,
)
from app.modules.account_shared.interfaces import (
    build_account_capabilities,
    list_workspace_accounts,
    lookup_account,
)
from app.modules.account_safety.risk import build_risk_by_operation, overall_risk_level

__all__ = [
    "build_account_safety",
    "build_account_safety_for_account",
    "build_account_safety_summary",
    "summarize_account_safety",
    "safety_preview_fields",
    "safety_preview_fields_with_policy",
    "unique_preserve_order",
]


def build_account_safety(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
) -> dict[str, Any]:
    account = lookup_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    return build_account_safety_for_account(session, account, config=config)


def build_account_safety_for_account(
    session: Session, account: Account, *, config: Settings = settings
) -> dict[str, Any]:
    checked_at = utc_now()
    health = collect_account_health_signals(session, account)
    capabilities = build_account_capabilities(
        account, health["reasons"], config=config, checked_at=checked_at
    )
    cooldowns_by_operation = merge_cooldowns(
        active_cooldowns_by_operation(session, account.id, now=checked_at),
        recent_failure_cooldowns_by_operation(session, account.id, config=config),
        product_cooldowns_by_operation(session, account.id, config=config, now=checked_at),
    )
    risk_by_operation = build_risk_by_operation(
        health["reasons"], capabilities, cooldowns_by_operation
    )
    last_validity_check = _latest_validity_check(session, account.id)
    overrides = active_overrides_by_operation(
        session,
        account.id,
        workspace_id=account.workspace_id,
        now=checked_at,
    )
    return _build_safety_result(
        account,
        health=health,
        capabilities=capabilities,
        cooldowns_by_operation=cooldowns_by_operation,
        risk_by_operation=risk_by_operation,
        overrides_by_operation=overrides,
        last_validity_check=last_validity_check,
        checked_at=checked_at,
    )


def build_account_safety_summary(
    session: Session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    config: Settings = settings,
) -> list[dict[str, Any]]:
    accounts = list_workspace_accounts(session, workspace_id=workspace_id)
    if not accounts:
        return []
    account_ids = [a.id for a in accounts]
    checked_at = utc_now()

    latest_jobs_map = batch_latest_jobs(session, account_ids, workspace_id=workspace_id)
    latest_failed_steps_map = batch_latest_failed_steps(
        session, account_ids, workspace_id=workspace_id
    )
    active_cooldowns_map = batch_active_cooldowns_by_operation(session, account_ids, now=checked_at)
    recent_failed_map = batch_recent_failed_steps(session, account_ids)
    succeeded_steps_map = batch_latest_succeeded_steps(session, account_ids)
    validity_map = _batch_latest_validity_checks(session, account_ids)
    overrides_map = batch_active_overrides_by_operation(
        session,
        account_ids,
        workspace_id=workspace_id,
        now=checked_at,
    )

    results: list[dict[str, Any]] = []
    for account in accounts:
        health = collect_account_health_signals_prefetched(
            account,
            latest_jobs_map.get(account.id),
            latest_failed_steps_map.get(account.id),
        )
        capabilities = build_account_capabilities(
            account, health["reasons"], config=config, checked_at=checked_at
        )
        cooldowns_by_operation = merge_cooldowns(
            active_cooldowns_map.get(account.id, {}),
            recent_failure_cooldowns_from_steps(
                recent_failed_map.get(account.id, []),
                account.id,
                config=config,
            ),
            product_cooldowns_from_steps(
                succeeded_steps_map,
                account.id,
                config=config,
                now=checked_at,
            ),
        )
        risk_by_operation = build_risk_by_operation(
            health["reasons"], capabilities, cooldowns_by_operation
        )
        last_validity_check = validity_map.get(account.id)
        safety = _build_safety_result(
            account,
            health=health,
            capabilities=capabilities,
            cooldowns_by_operation=cooldowns_by_operation,
            risk_by_operation=risk_by_operation,
            overrides_by_operation=overrides_map.get(account.id, {}),
            last_validity_check=last_validity_check,
            checked_at=checked_at,
        )
        results.append(summarize_account_safety(safety))
    return results


def summarize_account_safety(safety: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": safety["account_id"],
        "health_status": safety["health_status"],
        "overall_risk_level": safety["overall_risk_level"],
        "validity_status": safety["validity_status"],
        "proxy_status": safety.get("proxy_status", "none"),
        "capability_summary": safety["capability_summary"],
        "cooldown_summary": _cooldown_summary(safety["cooldowns_by_operation"]),
        "top_reasons": safety["top_reasons"],
        "last_checked_at": safety["last_checked_at"],
        "source": safety["source"],
    }


def _top_reasons(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    severity_order = {"blocked": 3, "high": 2, "medium": 1, "low": 0}
    return sorted(
        reasons, key=lambda reason: severity_order.get(str(reason["severity"]), 0), reverse=True
    )[:2]


def _cooldown_summary(
    cooldowns_by_operation: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cooldowns = [item for items in cooldowns_by_operation.values() for item in items]
    return sorted(cooldowns, key=lambda item: item["retry_after_at"], reverse=True)[:2]


def _overall_account_risk(
    reasons: list[dict[str, Any]], risk_by_operation: dict[str, dict[str, Any]]
) -> str:
    if any(reason["severity"] == "blocked" for reason in reasons):
        return "blocked"
    if any(reason["severity"] == "high" for reason in reasons):
        return "high"
    if any(reason["severity"] == "medium" for reason in reasons):
        return "medium"
    if not reasons:
        return "low"
    profile_risks = {
        key: risk_by_operation[key]
        for key in ("profile_update", "username", "profile_photo", "profile_music", "sync")
        if key in risk_by_operation
    }
    return overall_risk_level(profile_risks) if profile_risks else "unknown"


def _batch_latest_validity_checks(
    session: Session, account_ids: list[str]
) -> dict[str, dict[str, Any] | None]:
    """Fetch latest validity check per account in one query."""
    if not account_ids:
        return {}
    rows = (
        session.execute(
            select(AccountValidityCheckRun)
            .where(AccountValidityCheckRun.account_id.in_(account_ids))
            .order_by(AccountValidityCheckRun.account_id, AccountValidityCheckRun.started_at.desc())
        )
        .scalars()
        .all()
    )
    result: dict[str, dict[str, Any] | None] = {}
    for run in rows:
        if run.account_id not in result:
            result[run.account_id] = {
                "id": run.id,
                "account_id": run.account_id,
                "mode": run.mode,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "error_code": run.error_code,
                "error_class": run.error_class,
                "details": run.details_json,
                "result": run.result_json,
                "created_at": run.created_at,
            }
    return result


def _latest_validity_check(session: Session, account_id: str) -> dict[str, Any] | None:
    run = (
        session.execute(
            select(AccountValidityCheckRun)
            .where(AccountValidityCheckRun.account_id == account_id)
            .order_by(AccountValidityCheckRun.started_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if run is None:
        return None
    return {
        "id": run.id,
        "account_id": run.account_id,
        "mode": run.mode,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_code": run.error_code,
        "error_class": run.error_class,
        "details": run.details_json,
        "result": run.result_json,
        "created_at": run.created_at,
    }


def _validity_status_from_check(check: dict[str, Any] | None) -> str:
    if not check:
        return "db_snapshot"
    if check.get("status") == "running":
        return "db_snapshot"
    raw_result = check.get("result")
    result = cast(dict[str, Any], raw_result) if isinstance(raw_result, dict) else {}
    if result.get("validity_status"):
        return str(result["validity_status"])
    return str(check["status"])


def _build_safety_result(
    account: Account,
    *,
    health: dict[str, Any],
    capabilities: dict[str, Any],
    cooldowns_by_operation: dict[str, list[dict[str, Any]]],
    risk_by_operation: dict[str, dict[str, Any]],
    overrides_by_operation: dict[str, list[dict[str, Any]]],
    last_validity_check: dict[str, Any] | None,
    checked_at: datetime,
) -> dict[str, Any]:
    return {
        "account_id": account.id,
        "health_status": health["health_status"],
        "overall_risk_level": _overall_account_risk(health["reasons"], risk_by_operation),
        "validity_status": _validity_status_from_check(last_validity_check),
        "proxy_status": _proxy_status(account.proxy),
        "capabilities": capabilities,
        "capability_summary": {key: value["state"] for key, value in capabilities.items()},
        "risk_by_operation": risk_by_operation,
        "cooldowns_by_operation": cooldowns_by_operation,
        "active_overrides_by_operation": overrides_by_operation,
        "reasons": health["reasons"],
        "top_reasons": _top_reasons(health["reasons"]),
        "last_checked_at": checked_at,
        "source": "db_snapshot",
        "last_validity_check": last_validity_check,
    }


def _proxy_status(proxy: AccountProxy | None) -> str:
    if proxy is None:
        return "none"
    return proxy.status
