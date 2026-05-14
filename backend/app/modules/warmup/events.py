from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.models import WarmupEvent, WarmupSession, new_id


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
) -> WarmupEvent:
    event = WarmupEvent(
        id=new_id(),
        workspace_id=warmup_session.workspace_id,
        session_id=warmup_session.id,
        event_type=event_type,
        payload_json=_sanitize_event_payload(payload or {}),
    )
    session.add(event)
    return event


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
    "SENSITIVE_EVENT_KEYS",
    "write_warmup_event",
]
