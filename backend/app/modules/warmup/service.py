from __future__ import annotations

from app.config import settings
from app.modules.warmup.commands import (
    _build_proxy_snapshot,
    create_warmup_session,
    create_warmup_session_use_case,
    delete_warmup_session,
    delete_warmup_session_use_case,
    pause_warmup_session,
    pause_warmup_session_use_case,
    resume_warmup_session,
    resume_warmup_session_use_case,
    set_disabled_actions,
    set_disabled_actions_use_case,
)
from app.modules.warmup.action_presets import apply_action_preset_use_case
from app.modules.warmup.action_metadata import list_action_metadata
from app.modules.warmup.enqueue import enqueue_warmup_dispatch_tick, enqueue_warmup_due_sessions
from app.modules.warmup.errors import WarmupError
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.policies import is_warmup_active_status
from app.modules.warmup.queries import (
    get_warmup_isolation_status,
    get_warmup_readiness,
    get_warmup_session_detail,
    get_warmup_session_status,
    get_warmup_session_timer,
    list_warmup_event_feed_page,
    list_warmup_session_events_page,
    list_warmup_sessions_page,
    list_warmup_strategies,
    validate_warmup,
    warmup_operation_policy,
)
from app.modules.warmup.read_models import _strategy_read, session_read, session_summary
from app.modules.warmup.repository import (
    active_warmup_for_account,
    batch_active_warmups_for_accounts,
    get_warmup_session,
    list_warmup_events,
    list_warmup_sessions,
)


def warmup_error_to_status_code(exc: WarmupError, default: int) -> int:
    return exc.status_code or default


__all__ = [
    "_build_proxy_snapshot",
    "_strategy_read",
    "active_warmup_for_account",
    "apply_action_preset_use_case",
    "batch_active_warmups_for_accounts",
    "create_warmup_session",
    "create_warmup_session_use_case",
    "delete_warmup_session",
    "delete_warmup_session_use_case",
    "enqueue_warmup_dispatch_tick",
    "enqueue_warmup_due_sessions",
    "get_warmup_isolation_status",
    "get_warmup_readiness",
    "get_warmup_session",
    "get_warmup_session_detail",
    "get_warmup_session_status",
    "get_warmup_session_timer",
    "is_warmup_active_status",
    "list_warmup_events",
    "list_action_metadata",
    "list_warmup_event_feed_page",
    "list_warmup_session_events_page",
    "list_warmup_sessions",
    "list_warmup_sessions_page",
    "list_warmup_strategies",
    "pause_warmup_session",
    "pause_warmup_session_use_case",
    "resume_warmup_session",
    "resume_warmup_session_use_case",
    "set_disabled_actions",
    "set_disabled_actions_use_case",
    "session_read",
    "session_summary",
    "settings",
    "validate_warmup",
    "warmup_error_to_status_code",
    "warmup_operation_policy",
    "write_warmup_event",
]
