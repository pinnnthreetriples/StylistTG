from __future__ import annotations

from app.modules.warmup.channel_state.contracts import (
    ChannelCapabilities,
    ChannelCapabilitiesAdapter,
    ChannelStateSnapshot,
)
from app.modules.warmup.channel_state.health import (
    HEALTH_THRESHOLD_EXCLUDE,
    HEALTH_THRESHOLD_WARN,
    compute_health_score,
    is_channel_healthy,
)
from app.modules.warmup.channel_state.repository import (
    get_states_for_account,
    mark_action_done,
    mark_action_failed,
    mark_channel_failure,
    mark_channel_success,
    update_capabilities,
    upsert_subscribed,
)
from app.modules.warmup.channel_state.service import (
    discover_capabilities,
    record_action_result,
)

__all__ = [
    "ChannelCapabilities",
    "ChannelCapabilitiesAdapter",
    "ChannelStateSnapshot",
    "HEALTH_THRESHOLD_EXCLUDE",
    "HEALTH_THRESHOLD_WARN",
    "compute_health_score",
    "discover_capabilities",
    "get_states_for_account",
    "is_channel_healthy",
    "mark_action_done",
    "mark_action_failed",
    "mark_channel_failure",
    "mark_channel_success",
    "record_action_result",
    "update_capabilities",
    "upsert_subscribed",
]
