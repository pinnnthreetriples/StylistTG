from __future__ import annotations

# pyright: reportUnknownVariableType=false

from dataclasses import dataclass, field
from typing import Any, Protocol


SUPPORTED_PASSIVE_ACTIONS: tuple[str, ...] = (
    "feed_read",
    "channel_browse",
    "view_dialogs",
    "scroll_channels",
    "mark_as_read",
    "search_messages",
    "vote_poll",
    "watch_video",
    "listen_voice",
    "search_gif",
    "view_stickers",
    "inline_bot",
    "link_preview",
    "view_story",
    "ping_proxy",
    "get_me",
)
SUPPORTED_NETWORK_ACTIONS: tuple[str, ...] = SUPPORTED_PASSIVE_ACTIONS + ("join_chat",)
SUPPORTED_ADVANCED_ACTIONS: tuple[str, ...] = SUPPORTED_NETWORK_ACTIONS + (
    "react_to_post",
    "p2p_send",
    "forward_message",
    "saved_messages",
    "sync_contacts",
    "archive_chat",
    "mute_chat",
)

SUPPORTED_ACTIONS_BY_MODE: dict[str, tuple[str, ...]] = {
    "passive": SUPPORTED_PASSIVE_ACTIONS,
    "network": SUPPORTED_NETWORK_ACTIONS,
    "advanced": SUPPORTED_ADVANCED_ACTIONS,
}

WRITE_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "join_chat",
        "react_to_post",
        "p2p_send",
        "forward_message",
        "saved_messages",
        "sync_contacts",
        "archive_chat",
        "mute_chat",
    }
)


def collect_supported_actions(modes: tuple[str, ...]) -> set[str]:
    out: set[str] = set()
    for mode in modes:
        out.update(SUPPORTED_ACTIONS_BY_MODE.get(mode, ()))
    return out


@dataclass(frozen=True)
class WarmupActionResult:
    status: str
    action_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    error_class: str | None = None
    error_code: str | None = None
    retry_after_seconds: int | None = None

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


class WarmupTdlibAdapter(Protocol):
    provider_name: str

    def is_available(self) -> bool: ...

    def supports_action(self, action_type: str) -> bool: ...

    def execute_action(
        self, *, account_id: str, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult: ...

    def close(self) -> None: ...
