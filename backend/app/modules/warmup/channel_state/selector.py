from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot

DEFAULT_ACTION_PRIORITY = (
    "feed_read",
    "view_dialogs",
    "mark_as_read",
    "channel_browse",
    "scroll_channels",
    "search_messages",
    "view_story",
    "join_chat",
    "react_to_post",
    "p2p_send",
)
CHANNEL_STALE_AFTER = timedelta(hours=6)


@dataclass(frozen=True)
class SelectedAction:
    action_type: str
    channel_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def choose_actions(
    *,
    plan: dict[str, int],
    counters: dict[str, int],
    channel_states: list[ChannelStateSnapshot],
    available_targets: list[str],
    rng: random.Random,
    now: datetime,
    max_actions: int = 3,
) -> list[SelectedAction]:
    """Return ordered action/channel pairs for one micro-session window."""
    states_by_ref = {state.channel_ref: state for state in channel_states}
    selected: list[SelectedAction] = []
    for action_type in _pending_action_types(plan, counters):
        if len(selected) >= max_actions:
            break
        if rng.random() >= 0.85:
            continue
        action = _select_action(
            action_type,
            states_by_ref=states_by_ref,
            available_targets=available_targets,
            rng=rng,
            now=now,
        )
        if action is not None:
            selected.append(action)
    return selected


def _pending_action_types(plan: dict[str, int], counters: dict[str, int]) -> list[str]:
    candidates = sorted(
        plan.keys(),
        key=lambda key: (
            DEFAULT_ACTION_PRIORITY.index(key)
            if key in DEFAULT_ACTION_PRIORITY
            else len(DEFAULT_ACTION_PRIORITY),
            key,
        ),
    )
    return [key for key in candidates if plan.get(key, 0) - counters.get(key, 0) > 0]


def _select_action(
    action_type: str,
    *,
    states_by_ref: dict[str, ChannelStateSnapshot],
    available_targets: list[str],
    rng: random.Random,
    now: datetime,
) -> SelectedAction | None:
    if action_type == "join_chat":
        candidates = [
            target
            for target in available_targets
            if states_by_ref.get(target) is None or states_by_ref[target].subscribed_at is None
        ]
        if not candidates:
            return None if available_targets else SelectedAction(action_type)
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "not_subscribed"})
    if action_type == "channel_browse":
        candidates = [
            state.channel_ref
            for state in states_by_ref.values()
            if state.subscribed_at is not None and _is_stale(state.last_browse_at, now)
        ]
        if not candidates:
            return None if available_targets or states_by_ref else SelectedAction(action_type)
        return SelectedAction(
            action_type, _pick(candidates, rng), {"reason": "never_browsed_or_stale"}
        )
    if action_type == "scroll_channels":
        candidates = [
            state.channel_ref
            for state in states_by_ref.values()
            if state.subscribed_at is not None and _is_stale(state.last_browse_at, now)
        ]
        if not candidates:
            return SelectedAction(action_type) if available_targets else None
        return SelectedAction(
            action_type, _pick(candidates, rng), {"reason": "subscribed_channel_stale"}
        )
    if action_type == "view_story":
        subscribed = [state for state in states_by_ref.values() if state.subscribed_at is not None]
        candidates = [
            state.channel_ref
            for state in subscribed
            if state.has_stories is True and _is_stale(state.last_story_view_at, now)
        ]
        if not candidates:
            if subscribed:
                return SelectedAction(
                    action_type, _pick([state.channel_ref for state in subscribed], rng)
                )
            return SelectedAction(action_type) if available_targets else None
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "story_available"})
    if action_type == "react_to_post":
        subscribed = [state for state in states_by_ref.values() if state.subscribed_at is not None]
        candidates = [
            state.channel_ref
            for state in subscribed
            if state.has_reactions is True
            and state.available_reactions
            and _is_stale(state.last_react_at, now)
        ]
        if not candidates:
            if subscribed:
                return SelectedAction(
                    action_type, _pick([state.channel_ref for state in subscribed], rng)
                )
            return SelectedAction(action_type) if available_targets else None
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "reaction_available"})
    if action_type == "p2p_send":
        return SelectedAction(action_type, None, {"reason": "peer_selected_in_context"})
    return SelectedAction(action_type)


def _is_stale(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return True
    if value.tzinfo is None and now.tzinfo is not None:
        value = value.replace(tzinfo=now.tzinfo)
    if value.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=value.tzinfo)
    return now - value >= CHANNEL_STALE_AFTER


def _pick(candidates: list[str], rng: random.Random) -> str:
    return candidates[rng.randint(0, len(candidates) - 1)]
