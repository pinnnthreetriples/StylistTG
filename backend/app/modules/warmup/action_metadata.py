from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS, WRITE_ACTION_TYPES

ActionCategory = Literal["reading", "activity", "entertainment", "social", "groups", "profile"]

TRAFFIC_HEAVY_ACTIONS: frozenset[str] = frozenset(
    {
        "scroll_channels",
        "watch_video",
        "listen_voice",
        "search_gif",
        "view_stickers",
        "link_preview",
    }
)
REQUIRES_PREMIUM_ACTIONS: frozenset[str] = frozenset({"emoji_status"})

_ACTION_CATEGORIES: dict[str, ActionCategory] = {
    "feed_read": "reading",
    "channel_browse": "reading",
    "view_dialogs": "reading",
    "scroll_channels": "reading",
    "mark_as_read": "reading",
    "search_messages": "reading",
    "view_story": "reading",
    "vote_poll": "activity",
    "watch_video": "activity",
    "listen_voice": "activity",
    "react_to_post": "activity",
    "search_gif": "entertainment",
    "view_stickers": "entertainment",
    "inline_bot": "entertainment",
    "link_preview": "entertainment",
    "p2p_send": "social",
    "forward_message": "social",
    "saved_messages": "social",
    "sync_contacts": "social",
    "join_chat": "groups",
    "archive_chat": "groups",
    "mute_chat": "groups",
    "simulate_typing": "profile",
    "view_profile": "profile",
    "check_settings": "profile",
    "emoji_status": "profile",
    "drafts": "profile",
    "scheduled_messages": "profile",
    "update_profile_gradual": "profile",
    "notification_settings": "profile",
    "ping_proxy": "profile",
    "get_me": "profile",
}


@dataclass(frozen=True)
class ActionMetadata:
    action_type: str
    category: ActionCategory
    traffic_heavy: bool
    write_action: bool
    requires_premium: bool = False


def is_traffic_heavy(action_type: str) -> bool:
    return action_type in TRAFFIC_HEAVY_ACTIONS


def list_action_metadata() -> list[ActionMetadata]:
    return [
        ActionMetadata(
            action_type=action_type,
            category=_ACTION_CATEGORIES[action_type],
            traffic_heavy=is_traffic_heavy(action_type),
            write_action=action_type in WRITE_ACTION_TYPES,
            requires_premium=action_type in REQUIRES_PREMIUM_ACTIONS,
        )
        for action_type in SUPPORTED_ADVANCED_ACTIONS
    ]


__all__ = [
    "ActionCategory",
    "ActionMetadata",
    "TRAFFIC_HEAVY_ACTIONS",
    "is_traffic_heavy",
    "list_action_metadata",
]
