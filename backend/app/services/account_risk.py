from __future__ import annotations

from typing import Any


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
            for operation in ("profile_update", "username", "profile_photo", "profile_music", "story_post"):
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
            reason = {
                "code": cooldown["reason_code"],
                "severity": level,
                "source": cooldown["source"],
                "message": "Активна пауза безопасности для операции",
                "last_seen_at": cooldown["started_at"],
            }
            risks[operation] = _max_risk(risks.get(operation, _risk("low", [])), level, [reason])

    return risks


def overall_risk_level(risk_by_operation: dict[str, dict[str, Any]]) -> str:
    return max((risk["level"] for risk in risk_by_operation.values()), key=lambda level: RISK_ORDER[level])


def _risk(level: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
    return {"level": level, "reasons": reasons}


def _max_risk(current: dict[str, Any], level: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
    if RISK_ORDER[level] > RISK_ORDER[current["level"]]:
        return _risk(level, reasons)
    if RISK_ORDER[level] == RISK_ORDER[current["level"]] and reasons:
        return {"level": current["level"], "reasons": [*current["reasons"], *reasons]}
    return current
