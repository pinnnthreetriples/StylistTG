from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.models import WarmupEvent, WarmupSession, new_id

WARMUP_EVENT_SEVERITIES = {"info", "success", "warning", "error", "debug"}

EVENT_SEVERITY_DEFAULTS = {
    "action_executed_ok": "success",
    "channel_blacklisted": "warning",
    "circuit_breaker_triggered": "error",
    "circuit_breaker_tripped": "error",
    "dispatch_skipped_cold_soak": "debug",
    "p2p_contact_recording_failed": "warning",
    "queue_enqueue_failed": "error",
    "session_action_executed": "success",
    "session_action_simulated": "success",
    "task_executed": "success",
    "task_failed": "error",
    "warmup_dispatch_blocked_by_gate": "warning",
}

SKIP_WARNING_REASONS = {"safety_gate_blocked", "flood_wait"}

SENSITIVE_EVENT_KEYS = {
    "api_hash",
    "api_key",
    "auth_key",
    "password",
    "proxy_password",
    "session",
    "session_string",
    "tdlib_path",
}


def write_warmup_event(
    session: Session,
    warmup_session: WarmupSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    severity: str | None = None,
) -> WarmupEvent:
    sanitized_payload = _sanitize_event_payload(payload or {})
    resolved_severity = _resolve_event_severity(
        event_type, sanitized_payload, explicit_severity=severity
    )
    event = WarmupEvent(
        id=new_id(),
        workspace_id=warmup_session.workspace_id,
        session_id=warmup_session.id,
        event_type=event_type,
        severity=resolved_severity,
        payload_json=sanitized_payload,
    )
    session.add(event)
    return event


def _resolve_event_severity(
    event_type: str,
    payload: dict[str, Any],
    *,
    explicit_severity: str | None,
) -> str:
    if explicit_severity is not None:
        if explicit_severity not in WARMUP_EVENT_SEVERITIES:
            raise ValueError(f"invalid warmup event severity: {explicit_severity}")
        return explicit_severity
    if event_type == "task_skipped":
        reason = str(payload.get("reason") or "")
        if reason in SKIP_WARNING_REASONS:
            return "warning"
        if reason == "cyclic_inactive_window":
            return "debug"
        return "info"
    if event_type == "micro_session_window_opened":
        return "info"
    return EVENT_SEVERITY_DEFAULTS.get(event_type, "info")


def _sanitize_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_EVENT_KEYS:
            sanitized[key] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_event_payload(cast(dict[str, Any], value))
        elif isinstance(value, list):
            items = cast(list[object], value)
            sanitized[key] = [
                _sanitize_event_payload(cast(dict[str, Any], item))
                if isinstance(item, dict)
                else item
                for item in items
            ]
        else:
            sanitized[key] = value
    return sanitized


__all__ = [
    "EVENT_SEVERITY_DEFAULTS",
    "SENSITIVE_EVENT_KEYS",
    "WARMUP_EVENT_SEVERITIES",
    "_resolve_event_severity",
    "write_warmup_event",
]
