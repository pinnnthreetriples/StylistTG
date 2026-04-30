from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import Account, AccountValidityCheckRun
from app.services.account_capabilities import build_account_capabilities
from app.services.account_health import collect_account_health_signals
from app.services.account_risk import build_risk_by_operation, overall_risk_level
from app.services.accounts import get_account, list_accounts


def build_account_safety(session: Session, account_id: str, *, config: Settings = settings) -> dict[str, Any]:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    return build_account_safety_for_account(session, account, config=config)


def build_account_safety_for_account(session: Session, account: Account, *, config: Settings = settings) -> dict[str, Any]:
    checked_at = datetime.now(UTC)
    health = collect_account_health_signals(session, account)
    capabilities = build_account_capabilities(account, health["reasons"], config=config, checked_at=checked_at)
    risk_by_operation = build_risk_by_operation(health["reasons"], capabilities)
    return {
        "account_id": account.id,
        "health_status": health["health_status"],
        "overall_risk_level": _overall_account_risk(health["reasons"], risk_by_operation),
        "validity_status": "db_snapshot",
        "capabilities": capabilities,
        "capability_summary": {key: value["state"] for key, value in capabilities.items()},
        "risk_by_operation": risk_by_operation,
        "reasons": health["reasons"],
        "top_reasons": _top_reasons(health["reasons"]),
        "last_checked_at": checked_at,
        "source": "db_snapshot",
        "last_validity_check": _latest_validity_check(session, account.id),
    }


def build_account_safety_summary(session: Session, *, config: Settings = settings) -> list[dict[str, Any]]:
    return [summarize_account_safety(build_account_safety_for_account(session, account, config=config)) for account in list_accounts(session)]


def summarize_account_safety(safety: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": safety["account_id"],
        "health_status": safety["health_status"],
        "overall_risk_level": safety["overall_risk_level"],
        "validity_status": safety["validity_status"],
        "capability_summary": safety["capability_summary"],
        "top_reasons": safety["top_reasons"],
        "last_checked_at": safety["last_checked_at"],
        "source": safety["source"],
    }


def safety_preview_fields(safety: dict[str, Any], desired_state: dict[str, Any]) -> dict[str, Any]:
    blockers = [reason["code"] for reason in safety["reasons"] if reason["severity"] == "blocked"]
    warnings = [reason["code"] for reason in safety["reasons"] if reason["severity"] != "blocked"]

    profile_audio = desired_state.get("profile_audio") or {}
    if profile_audio.get("action") in {"add", "remove"} and safety["capabilities"]["profile_music"]["state"] == "unknown":
        warnings.append("music_capability_not_checked")
    if desired_state.get("stories") and safety["capabilities"]["story_post"]["state"] == "blocked":
        blockers.extend(safety["capabilities"]["story_post"]["reason_codes"])

    return {
        "account_safety": safety,
        "risk_by_operation": safety["risk_by_operation"],
        "safety_warnings": _unique(warnings),
        "safety_blockers": _unique(blockers),
    }


def _top_reasons(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    severity_order = {"blocked": 3, "high": 2, "medium": 1, "low": 0}
    return sorted(reasons, key=lambda reason: severity_order.get(str(reason["severity"]), 0), reverse=True)[:2]


def _overall_account_risk(reasons: list[dict[str, Any]], risk_by_operation: dict[str, dict[str, Any]]) -> str:
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


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _latest_validity_check(session: Session, account_id: str) -> dict[str, Any] | None:
    run = session.execute(
        select(AccountValidityCheckRun)
        .where(AccountValidityCheckRun.account_id == account_id)
        .order_by(AccountValidityCheckRun.started_at.desc())
        .limit(1)
    ).scalars().first()
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
