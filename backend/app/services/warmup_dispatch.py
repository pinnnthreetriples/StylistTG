from __future__ import annotations

from app.modules.warmup import dispatcher as _dispatcher
from app.modules.warmup.dispatcher import (
    DEFAULT_ACTION_PRIORITY,
    MAX_ACTIONS_PER_MICRO_SESSION,
    process_due_warmup_dispatches,
)

_ActionContextResolution = getattr(_dispatcher, "_ActionContextResolution")
_complete_dispatch_session = getattr(_dispatcher, "_complete_dispatch_session")
_derive_text_seed = getattr(_dispatcher, "_derive_text_seed")
_execute_live_action = getattr(_dispatcher, "_execute_live_action")
_is_day_complete = getattr(_dispatcher, "_is_day_complete")
_is_hour_in_quiet_window = getattr(_dispatcher, "_is_hour_in_quiet_window")
_is_in_quiet_hours = getattr(_dispatcher, "_is_in_quiet_hours")
_isolation_owner = getattr(_dispatcher, "_isolation_owner")
_local_hour = getattr(_dispatcher, "_local_hour")
_max_retry_after_seconds = getattr(_dispatcher, "_max_retry_after_seconds")
_next_day_first_window = getattr(_dispatcher, "_next_day_first_window")
_next_quiet_hours_end = getattr(_dispatcher, "_next_quiet_hours_end")
_persist_day_counters = getattr(_dispatcher, "_persist_day_counters")
_process_one_dispatch = getattr(_dispatcher, "_process_one_dispatch")
_resolve_action_context = getattr(_dispatcher, "_resolve_action_context")
_resolve_day_counters = getattr(_dispatcher, "_resolve_day_counters")
_resolve_day_plan = getattr(_dispatcher, "_resolve_day_plan")
_resolve_timezone = getattr(_dispatcher, "_resolve_timezone")
_schedule_within_day = getattr(_dispatcher, "_schedule_within_day")
_select_actions_for_window = getattr(_dispatcher, "_select_actions_for_window")
_select_chat_target = getattr(_dispatcher, "_select_chat_target")

__all__ = [
    "DEFAULT_ACTION_PRIORITY",
    "MAX_ACTIONS_PER_MICRO_SESSION",
    "_ActionContextResolution",
    "_complete_dispatch_session",
    "_derive_text_seed",
    "_execute_live_action",
    "_is_day_complete",
    "_is_hour_in_quiet_window",
    "_is_in_quiet_hours",
    "_isolation_owner",
    "_local_hour",
    "_max_retry_after_seconds",
    "_next_day_first_window",
    "_next_quiet_hours_end",
    "_persist_day_counters",
    "_process_one_dispatch",
    "_resolve_action_context",
    "_resolve_day_counters",
    "_resolve_day_plan",
    "_resolve_timezone",
    "_schedule_within_day",
    "_select_actions_for_window",
    "_select_chat_target",
    "process_due_warmup_dispatches",
]
