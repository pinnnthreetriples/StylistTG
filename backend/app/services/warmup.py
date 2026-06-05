"""Compatibility wrapper.

Canonical owner: app.modules.warmup.service
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.warmup import events as _events
from app.modules.warmup import service as _service
from app.modules.warmup.events import SENSITIVE_EVENT_KEYS, write_warmup_event
from app.modules.warmup.repository import (
    active_warmup_for_account,
    batch_active_warmups_for_accounts,
    get_warmup_session,
    list_warmup_events,
    list_warmup_sessions,
)
from app.modules.warmup.service import (
    create_warmup_session,
    delete_warmup_session,
    is_warmup_active_status,
    pause_warmup_session,
    resume_warmup_session,
    set_disabled_actions,
    warmup_operation_policy,
)

_build_proxy_snapshot = getattr(_service, "_build_proxy_snapshot")
_sanitize_event_payload = getattr(_events, "_sanitize_event_payload")

__all__ = [
    "SENSITIVE_EVENT_KEYS",
    "_build_proxy_snapshot",
    "_sanitize_event_payload",
    "active_warmup_for_account",
    "batch_active_warmups_for_accounts",
    "create_warmup_session",
    "delete_warmup_session",
    "get_warmup_session",
    "is_warmup_active_status",
    "list_warmup_events",
    "list_warmup_sessions",
    "pause_warmup_session",
    "resume_warmup_session",
    "set_disabled_actions",
    "warmup_operation_policy",
    "write_warmup_event",
]
