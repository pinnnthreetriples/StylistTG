from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.modules.account_safety.read_models import build_account_safety

BATCH_STATUSES = ("ready", "needs_login", "paused", "limited", "blocked", "unknown")


def build_account_batch_safety_preview(
    session: Session,
    *,
    account_ids: list[str],
    operation: str,
    allow_warning_overrides: bool = False,
    workspace_id: str | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    items = [
        _build_item(build_account_safety(session, account_id, config=config), operation)
        for account_id in account_ids
        if workspace_id is None or _account_in_workspace(session, account_id, workspace_id)
    ]
    if len(items) != len(account_ids):
        raise ValueError("account not found")
    blocking_account_ids = [
        item["account_id"]
        for item in items
        if item["batch_status"] in {"needs_login", "blocked", "paused"}
    ]
    warning_account_ids = [
        item["account_id"] for item in items if item["batch_status"] in {"limited", "unknown"}
    ]
    counts = {status: 0 for status in BATCH_STATUSES}
    for item in items:
        counts[item["batch_status"]] += 1
    return {
        "operation": operation,
        "can_start": not blocking_account_ids
        and (allow_warning_overrides or not warning_account_ids),
        "counts": counts,
        "blocking_account_ids": blocking_account_ids,
        "warning_account_ids": warning_account_ids,
        "items": items,
    }


def _build_item(safety: dict[str, Any], operation: str) -> dict[str, Any]:
    risk = safety["risk_by_operation"].get(
        operation, {"level": safety["overall_risk_level"], "reasons": []}
    )
    cooldowns = safety["cooldowns_by_operation"].get(operation, [])
    status = _batch_status(safety, risk["level"], cooldowns)
    return {
        "account_id": safety["account_id"],
        "batch_status": status,
        "health_status": safety["health_status"],
        "risk_level": risk["level"],
        "reasons": _item_reasons(safety, risk),
        "cooldowns": cooldowns,
    }


def _batch_status(safety: dict[str, Any], risk_level: str, cooldowns: list[dict[str, Any]]) -> str:
    if safety["health_status"] == "blocked":
        return "needs_login"
    if any(cooldown["level"] == "blocked" for cooldown in cooldowns):
        return "paused"
    if risk_level == "blocked":
        return "blocked"
    if risk_level in {"medium", "high"} or safety["health_status"] == "attention":
        return "limited"
    if safety["health_status"] == "ready":
        return "ready"
    return "unknown"


def _item_reasons(safety: dict[str, Any], risk: dict[str, Any]) -> list[dict[str, Any]]:
    reasons = list(risk.get("reasons") or safety["top_reasons"])
    if not reasons and safety["health_status"] == "ready":
        return []
    return reasons[:2]


def _account_in_workspace(session: Session, account_id: str, workspace_id: str) -> bool:
    from app.modules.account_core.interfaces import lookup_account

    return lookup_account(session, account_id, workspace_id=workspace_id) is not None
