from __future__ import annotations

import random
from hashlib import sha256
from typing import Any, cast

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS

FAVORITE_EMOJI_POOL: tuple[str, ...] = ("👍", "❤️", "🔥", "😁", "🎉", "👏", "🤔")
SESSION_LENGTH_PREFS: tuple[str, ...] = ("short", "medium", "long")
PACE_PREFS: tuple[str, ...] = ("slow", "normal", "fast")
_PREFERRED_HOUR_POOL: tuple[int, ...] = tuple(range(7, 23))


def generate_personality_seed(
    account_id: str,
    *,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    picker = rng or _account_rng(account_id)
    preferred_hours = sorted(picker.sample(list(_PREFERRED_HOUR_POOL), k=picker.randint(4, 7)))
    return {
        "account_id": account_id,
        "preferred_hours": preferred_hours,
        "typing_speed_cps": round(picker.uniform(4.0, 8.0), 2),
        "favorite_emojis": picker.sample(list(FAVORITE_EMOJI_POOL), k=3),
        "session_length_pref": picker.choice(SESSION_LENGTH_PREFS),
        "pace": picker.choice(PACE_PREFS),
        "action_preferences": {
            action_type: round(picker.uniform(0.65, 1.35), 3)
            for action_type in SUPPORTED_ADVANCED_ACTIONS
        },
    }


def choose_reaction(
    reactions: list[str],
    *,
    personality_seed: dict[str, Any] | None,
    rng: random.Random,
) -> str:
    favorites = favorite_reactions(reactions, personality_seed=personality_seed)
    if favorites and rng.random() < 0.7:
        return favorites[rng.randint(0, len(favorites) - 1)]
    return reactions[rng.randint(0, len(reactions) - 1)]


def favorite_reactions(
    reactions: list[str],
    *,
    personality_seed: dict[str, Any] | None,
) -> list[str]:
    available = set(reactions)
    seed = personality_seed or {}
    raw = seed.get("favorite_emojis")
    if not isinstance(raw, list):
        return []
    emojis = cast(list[object], raw)
    return [emoji for emoji in emojis if isinstance(emoji, str) and emoji in available]


def deterministic_reaction_rng(
    *,
    personality_seed: dict[str, Any] | None,
    channel_ref: str,
    current_day: Any,
) -> random.Random:
    account_id = (personality_seed or {}).get("account_id") or "account"
    raw = f"{account_id}|{current_day}|{channel_ref}|react_to_post"
    digest = sha256(raw.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _account_rng(account_id: str) -> random.Random:
    digest = sha256(account_id.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


__all__ = [
    "FAVORITE_EMOJI_POOL",
    "choose_reaction",
    "deterministic_reaction_rng",
    "favorite_reactions",
    "generate_personality_seed",
]
