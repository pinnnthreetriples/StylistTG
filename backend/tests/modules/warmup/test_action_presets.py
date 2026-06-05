from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS
from app.modules.warmup.action_presets import (
    ALL_ACTIONS,
    ECONOMIC_ACTIONS,
    MINIMAL_ACTIONS,
    apply_action_preset,
)


def test_action_preset_constants_cover_supported_advanced_actions() -> None:
    assert ALL_ACTIONS == SUPPORTED_ADVANCED_ACTIONS
    assert set(MINIMAL_ACTIONS) == {"feed_read", "view_dialogs"}
    assert set(ECONOMIC_ACTIONS) == {
        "feed_read",
        "view_dialogs",
        "mark_as_read",
        "search_messages",
        "saved_messages",
        "check_settings",
    }


def test_apply_economic_preset_keeps_existing_limits_and_disables_other_actions() -> None:
    result = apply_action_preset(
        {
            "1": {
                "feed_read": 5,
                "view_dialogs": 0,
                "scroll_channels": 4,
                "search_gif": 2,
            }
        },
        "economic",
        duration_days=14,
    )

    assert result["1"]["feed_read"] == 5
    assert result["1"]["view_dialogs"] == 1
    assert result["1"]["mark_as_read"] == 1
    assert result["1"]["scroll_channels"] == 0
    assert result["1"]["search_gif"] == 0


def test_apply_minimal_preset_builds_duration_days_when_limits_empty() -> None:
    result = apply_action_preset(None, "minimal", duration_days=2)

    assert list(result) == ["1", "2"]
    assert result["1"]["feed_read"] == 1
    assert result["1"]["view_dialogs"] == 1
    assert result["1"]["join_chat"] == 0


def test_apply_all_preset_enables_every_supported_action() -> None:
    result = apply_action_preset({"2": {"p2p_send": 3}}, "all", duration_days=14)

    assert set(result["2"]) == set(ALL_ACTIONS)
    assert result["2"]["p2p_send"] == 3
    assert all(limit > 0 for limit in result["2"].values())
