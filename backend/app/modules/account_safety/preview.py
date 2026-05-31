"""Preview policy helpers for account safety read models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.config import Settings, settings
from app.models import utc_now
from app.modules.account_safety.overrides import NON_OVERRIDABLE_BLOCKERS


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


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = [
    "safety_preview_fields",
    "safety_preview_fields_with_policy",
    "unique_preserve_order",
]
