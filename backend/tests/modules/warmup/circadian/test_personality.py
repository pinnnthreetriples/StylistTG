from __future__ import annotations

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS
from app.modules.warmup.circadian.personality import generate_personality_seed


def test_generate_personality_seed_is_deterministic_per_account() -> None:
    first = generate_personality_seed("account-1")
    second = generate_personality_seed("account-1")

    assert first == second


def test_generate_personality_seed_varies_between_accounts() -> None:
    first = generate_personality_seed("account-1")
    second = generate_personality_seed("account-2")

    assert first["preferred_hours"] != second["preferred_hours"] or first != second


def test_generate_personality_seed_shape() -> None:
    seed = generate_personality_seed("account-1")

    assert seed["account_id"] == "account-1"
    assert 4 <= len(seed["preferred_hours"]) <= 7
    assert all(7 <= hour <= 22 for hour in seed["preferred_hours"])
    assert 4.0 <= seed["typing_speed_cps"] <= 8.0
    assert len(seed["favorite_emojis"]) == 3
    assert seed["session_length_pref"] in {"short", "medium", "long"}
    assert seed["pace"] in {"slow", "normal", "fast"}
    assert set(seed["action_preferences"]) == set(SUPPORTED_ADVANCED_ACTIONS)
