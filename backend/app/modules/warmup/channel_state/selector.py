from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot
from app.modules.warmup.channel_state.health import is_channel_healthy

DEFAULT_ACTION_PRIORITY = (
    "feed_read",
    "view_dialogs",
    "mark_as_read",
    "channel_browse",
    "scroll_channels",
    "search_messages",
    "vote_poll",
    "watch_video",
    "listen_voice",
    "search_gif",
    "view_stickers",
    "inline_bot",
    "link_preview",
    "view_story",
    "join_chat",
    "react_to_post",
    "p2p_send",
    "forward_message",
    "saved_messages",
    "sync_contacts",
    "archive_chat",
    "mute_chat",
    "simulate_typing",
    "view_profile",
    "check_settings",
    "emoji_status",
    "drafts",
    "scheduled_messages",
    "update_profile_gradual",
    "notification_settings",
)
CHANNEL_STALE_AFTER = timedelta(hours=6)
CHANNEL_ACTIVITY_ACTION_TYPES = frozenset({"vote_poll", "watch_video", "listen_voice"})
CHANNEL_SOCIAL_ACTION_TYPES = frozenset({"forward_message"})
CHANNEL_PROFILE_CHAT_ACTION_TYPES = frozenset({"simulate_typing", "drafts"})


@dataclass(frozen=True)
class SelectedAction:
    action_type: str
    channel_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: {})


def choose_actions(
    *,
    plan: dict[str, int],
    counters: dict[str, int],
    channel_states: list[ChannelStateSnapshot],
    available_targets: list[str],
    rng: random.Random,
    now: datetime,
    max_actions: int = 3,
    personality_seed: dict[str, Any] | None = None,
) -> list[SelectedAction]:
    """Return ordered action/channel pairs for one micro-session window."""
    states_by_ref = {
        state.channel_ref: state for state in channel_states if is_channel_healthy(state)
    }
    excluded_refs = {state.channel_ref for state in channel_states if not is_channel_healthy(state)}
    selected: list[SelectedAction] = []
    for action_type in _pending_action_types(plan, counters, personality_seed=personality_seed):
        if len(selected) >= max_actions:
            break
        if rng.random() >= 0.85:
            continue
        action = _select_action(
            action_type,
            states_by_ref=states_by_ref,
            excluded_refs=excluded_refs,
            available_targets=available_targets,
            rng=rng,
            now=now,
        )
        if action is not None:
            selected.append(action)
    return selected


def _pending_action_types(
    plan: dict[str, int],
    counters: dict[str, int],
    *,
    personality_seed: dict[str, Any] | None = None,
) -> list[str]:
    candidates = sorted(
        plan.keys(),
        key=lambda key: (
            -_action_preference(key, personality_seed),
            DEFAULT_ACTION_PRIORITY.index(key)
            if key in DEFAULT_ACTION_PRIORITY
            else len(DEFAULT_ACTION_PRIORITY),
            key,
        ),
    )
    return [key for key in candidates if plan.get(key, 0) - counters.get(key, 0) > 0]


def _action_preference(action_type: str, personality_seed: dict[str, Any] | None) -> float:
    raw = (personality_seed or {}).get("action_preferences")
    if not isinstance(raw, Mapping):
        return 1.0
    preferences = cast(Mapping[str, Any], raw)
    try:
        return max(0.1, min(3.0, float(preferences.get(action_type, 1.0))))
    except TypeError, ValueError:
        return 1.0


def _select_action(
    action_type: str,
    *,
    states_by_ref: dict[str, ChannelStateSnapshot],
    excluded_refs: set[str],
    available_targets: list[str],
    rng: random.Random,
    now: datetime,
) -> SelectedAction | None:
    if action_type == "join_chat":
        candidates = [
            target
            for target in available_targets
            if target not in excluded_refs
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
    if action_type in CHANNEL_ACTIVITY_ACTION_TYPES:
        candidates = [
            state.channel_ref for state in states_by_ref.values() if state.subscribed_at is not None
        ]
        if not candidates:
            return SelectedAction(action_type)
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "subscribed_channel"})
    if action_type in CHANNEL_SOCIAL_ACTION_TYPES:
        candidates = [
            state.channel_ref for state in states_by_ref.values() if state.subscribed_at is not None
        ]
        if not candidates:
            return SelectedAction(action_type)
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "subscribed_channel"})
    if action_type in CHANNEL_PROFILE_CHAT_ACTION_TYPES:
        candidates = [
            state.channel_ref for state in states_by_ref.values() if state.subscribed_at is not None
        ]
        if not candidates:
            return SelectedAction(action_type)
        return SelectedAction(action_type, _pick(candidates, rng), {"reason": "subscribed_channel"})
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
