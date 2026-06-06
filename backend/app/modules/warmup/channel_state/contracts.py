from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ChannelCapabilities:
    channel_ref: str
    has_stories: bool | None
    has_reactions: bool | None
    available_reactions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChannelStateSnapshot:
    channel_ref: str
    subscribed_at: datetime | None
    last_feed_read_at: datetime | None
    last_story_view_at: datetime | None
    last_react_at: datetime | None
    last_browse_at: datetime | None
    has_stories: bool | None
    has_reactions: bool | None
    available_reactions: tuple[str, ...]
    health_score: float


class ChannelCapabilitiesAdapter(Protocol):
    def discover_channel_capabilities(
        self, *, account_id: str, channel_ref: str
    ) -> ChannelCapabilities: ...
