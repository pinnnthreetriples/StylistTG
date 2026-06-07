from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot
from app.modules.warmup.channel_state.selector import SelectedAction, choose_actions


NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_choose_actions_cold_start_prefers_join_chat_for_target() -> None:
    selected = choose_actions(
        plan={"join_chat": 1, "channel_browse": 1},
        counters={},
        channel_states=[],
        available_targets=["@news", "@memes"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=3,
    )

    assert selected == [SelectedAction("join_chat", "@news", {"reason": "not_subscribed"})]


def test_choose_actions_boundary_empty_plan_returns_no_actions() -> None:
    selected = choose_actions(
        plan={},
        counters={},
        channel_states=[],
        available_targets=["@news"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=3,
    )

    assert selected == []


def test_choose_actions_partial_state_skips_repeat_join_and_picks_channel_work() -> None:
    selected = choose_actions(
        plan={"join_chat": 1, "channel_browse": 1, "view_story": 1, "react_to_post": 1},
        counters={},
        channel_states=[
            _state(
                "@news",
                subscribed=True,
                has_stories=True,
                has_reactions=True,
                available_reactions=("👍",),
                last_browse_at=NOW - timedelta(hours=8),
            )
        ],
        available_targets=["@news", "@memes"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=10,
    )

    pairs = {(item.action_type, item.channel_ref) for item in selected}
    assert ("join_chat", "@memes") in pairs
    assert ("channel_browse", "@news") in pairs
    assert ("view_story", "@news") in pairs
    assert ("react_to_post", "@news") in pairs
    assert ("join_chat", "@news") not in pairs


def test_choose_actions_full_state_respects_capabilities_and_counters() -> None:
    selected = choose_actions(
        plan={"join_chat": 1, "view_story": 1, "react_to_post": 2, "p2p_send": 1},
        counters={"react_to_post": 1},
        channel_states=[
            _state("@news", subscribed=True, has_stories=False, has_reactions=True),
            _state("@memes", subscribed=True, has_stories=True, has_reactions=False),
        ],
        available_targets=["@news", "@memes"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=10,
    )

    pairs = {(item.action_type, item.channel_ref) for item in selected}
    assert ("join_chat", "@news") not in pairs
    assert ("join_chat", "@memes") not in pairs
    assert ("view_story", "@memes") in pairs
    assert ("react_to_post", "@news") in pairs
    assert ("p2p_send", None) in pairs


def test_choose_actions_limit_zero_returns_empty_selection() -> None:
    selected = choose_actions(
        plan={"join_chat": 1},
        counters={},
        channel_states=[],
        available_targets=["@news"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=0,
    )

    assert selected == []


def test_choose_actions_excludes_unhealthy_channel_state() -> None:
    selected = choose_actions(
        plan={"join_chat": 1, "channel_browse": 1, "view_story": 1, "react_to_post": 1},
        counters={},
        channel_states=[
            _state(
                "@dead",
                subscribed=True,
                has_stories=True,
                has_reactions=True,
                health_score=0.24,
                last_browse_at=NOW - timedelta(hours=8),
            ),
            _state("@fresh", subscribed=False, health_score=0.24),
        ],
        available_targets=["@dead", "@fresh", "@new"],
        rng=_AlwaysPick(),
        now=NOW,
        max_actions=10,
    )

    pairs = {(item.action_type, item.channel_ref) for item in selected}
    assert ("channel_browse", "@dead") not in pairs
    assert ("view_story", "@dead") not in pairs
    assert ("react_to_post", "@dead") not in pairs
    assert ("join_chat", "@fresh") not in pairs
    assert ("join_chat", "@new") in pairs


def _state(
    channel_ref: str,
    *,
    subscribed: bool,
    has_stories: bool | None = None,
    has_reactions: bool | None = None,
    available_reactions: tuple[str, ...] = ("👍",),
    last_browse_at: datetime | None = None,
    health_score: float = 1.0,
) -> ChannelStateSnapshot:
    return ChannelStateSnapshot(
        channel_ref=channel_ref,
        subscribed_at=NOW - timedelta(days=1) if subscribed else None,
        last_feed_read_at=None,
        last_story_view_at=None,
        last_react_at=None,
        last_browse_at=last_browse_at,
        has_stories=has_stories,
        has_reactions=has_reactions,
        available_reactions=available_reactions,
        health_score=health_score,
    )


class _AlwaysPick(random.Random):
    def random(self) -> float:
        return 0.0

    def randint(self, a: int, b: int) -> int:
        del b
        return a
