from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from app.modules.account_safety.overrides import (
    NON_OVERRIDABLE_BLOCKERS,
    active_overrides_by_operation,
    batch_active_overrides_by_operation,
)
from app.modules.account_safety.risk import build_risk_by_operation, overall_risk_level
from app.services.account_capabilities import build_account_capabilities
from app.services.accounts import get_account, list_accounts


def build_account_safety(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
) -> dict[str, Any]:
    account = get_account(session, account_id)
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
    accounts = list_accounts(session, workspace_id=workspace_id)
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


def safety_preview_fields(safety: dict[str, Any], desired_state: dict[str, Any]) -> dict[str, Any]:
    return safety_preview_fields_with_policy(safety, desired_state, config=settings)


def safety_preview_fields_with_policy(
    safety: dict[str, Any],
    desired_state: dict[str, Any],
    *,
    config: Settings = settings,
) -> dict[str, Any]:
    blockers = [reason["code"] for reason in safety["reasons"] if reason["severity"] == "blocked"]
    warnings = [reason["code"] for reason in safety["reasons"] if reason["severity"] != "blocked"]
    desired_operations = _desired_operations(desired_state)

    profile_audio = cast(dict[str, Any], desired_state.get("profile_audio") or {})
    if (
        profile_audio.get("action") in {"add", "remove"}
        and safety["capabilities"]["profile_music"]["state"] == "unknown"
    ):
        _add_by_unknown_capability_policy(
            "music_capability_not_checked", blockers, warnings, config=config
        )
    if desired_state.get("stories") and safety["capabilities"]["story_post"]["state"] == "blocked":
        blockers.extend(safety["capabilities"]["story_post"]["reason_codes"])
    _add_fresh_validity_policy(safety, blockers, warnings, config=config)
    for operation in desired_operations:
        for cooldown in safety["cooldowns_by_operation"].get(operation, []):
            code = f"cooldown_active:{operation}"
            if cooldown["level"] == "blocked":
                blockers.append(code)
            else:
                warnings.append(code)
    operation_safety = _operation_safety(safety, desired_operations, blockers, warnings)
    blockers, warnings, operation_safety = _apply_active_overrides(
        safety,
        desired_operations,
        blockers,
        warnings,
        operation_safety,
    )

    return {
        "account_safety": safety,
        "risk_by_operation": safety["risk_by_operation"],
        "cooldowns_by_operation": safety["cooldowns_by_operation"],
        "safety_warnings": unique_preserve_order(warnings),
        "safety_blockers": unique_preserve_order(blockers),
        "operation_safety": operation_safety,
    }


def _desired_operations(desired_state: dict[str, Any]) -> set[str]:
    operations: set[str] = set()
    profile = cast(dict[str, Any], desired_state.get("profile") or {})
    if any(profile.get(key) is not None for key in ("name", "bio")):
        operations.add("profile_update")
    if profile.get("username") is not None:
        operations.add("username")
    if desired_state.get("profile_photo"):
        operations.add("profile_photo")
    profile_audio = cast(dict[str, Any], desired_state.get("profile_audio") or {})
    if profile_audio.get("action") in {"add", "remove"}:
        operations.add("profile_music")
    stories = cast(list[dict[str, Any]], desired_state.get("stories") or [])
    if stories:
        operations.add("story_post")
    return operations


def _operation_safety(
    safety: dict[str, Any],
    desired_operations: set[str],
    blockers: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for operation in sorted(desired_operations):
        op_blockers = _operation_codes(operation, blockers)
        op_warnings = _operation_codes(operation, warnings)
        cooldowns = safety["cooldowns_by_operation"].get(operation, [])
        state = "blocked" if op_blockers else "warning" if op_warnings else "ready"
        result.append(
            {
                "operation": operation,
                "state": state,
                "warnings": unique_preserve_order(op_warnings),
                "blockers": unique_preserve_order(op_blockers),
                "cooldowns": cooldowns,
                "can_override": bool(op_blockers)
                and all(code not in NON_OVERRIDABLE_BLOCKERS for code in op_blockers),
            }
        )
    return result


def _operation_codes(operation: str, codes: list[str]) -> list[str]:
    global_codes = {
        "account_not_execution_usable",
        "fresh_validity_required",
        "fresh_validity_stale",
        "reauth_required",
        "runtime_broken",
        "missing_tdlib_credentials",
    }
    result: list[str] = []
    for code in codes:
        if (
            code in global_codes
            or code.endswith(f":{operation}")
            or code == f"product_cooldown:{operation}"
        ):
            result.append(code)
        elif operation == "profile_music" and code == "music_capability_not_checked":
            result.append(code)
        elif operation == "story_post" and code.startswith("stories_"):
            result.append(code)
    return result


def _apply_active_overrides(
    safety: dict[str, Any],
    desired_operations: set[str],
    blockers: list[str],
    warnings: list[str],
    operation_safety: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    overrides_by_operation = cast(
        dict[str, list[dict[str, Any]]], safety.get("active_overrides_by_operation") or {}
    )
    if not overrides_by_operation:
        return blockers, warnings, operation_safety
    remaining_blockers = list(blockers)
    next_warnings = list(warnings)
    next_operation_safety: list[dict[str, Any]] = []
    for item in operation_safety:
        operation = item["operation"]
        override_codes = {
            code
            for override in overrides_by_operation.get(operation, [])
            for code in override.get("requested_blockers", [])
        }
        if operation not in desired_operations or not override_codes:
            next_operation_safety.append(item)
            continue
        item_blockers: list[str] = []
        item_warnings = list(item["warnings"])
        for code in item["blockers"]:
            if code in override_codes and code not in NON_OVERRIDABLE_BLOCKERS:
                item_warnings.append(f"override_applied:{operation}")
                if code in remaining_blockers:
                    remaining_blockers.remove(code)
                continue
            item_blockers.append(code)
        next_operation_safety.append(
            {
                **item,
                "state": "blocked" if item_blockers else "warning" if item_warnings else "ready",
                "blockers": unique_preserve_order(item_blockers),
                "warnings": unique_preserve_order(item_warnings),
                "can_override": bool(item_blockers)
                and all(code not in NON_OVERRIDABLE_BLOCKERS for code in item_blockers),
            }
        )
        if f"override_applied:{operation}" in item_warnings:
            next_warnings.append(f"override_applied:{operation}")
    return remaining_blockers, next_warnings, next_operation_safety


def _add_by_unknown_capability_policy(
    code: str,
    blockers: list[str],
    warnings: list[str],
    *,
    config: Settings,
) -> None:
    if config.unknown_capability_policy == "block_live_execution":
        blockers.append(code)
        return
    warnings.append(code)


def _add_fresh_validity_policy(
    safety: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    *,
    config: Settings,
) -> None:
    if config.fresh_validity_required == "never":
        return
    if not _validity_is_stale(safety, max_age_minutes=config.fresh_validity_max_age_minutes):
        return
    if config.fresh_validity_required == "always_for_live":
        blockers.append("fresh_validity_required")
        return
    warnings.append("fresh_validity_stale")


def _validity_is_stale(safety: dict[str, Any], *, max_age_minutes: int) -> bool:
    check = safety.get("last_validity_check")
    if not check or check.get("status") != "completed":
        return True
    finished_at = check.get("finished_at") or check.get("started_at")
    if not isinstance(finished_at, datetime):
        return True
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    return utc_now() - finished_at > timedelta(minutes=max_age_minutes)


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


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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
