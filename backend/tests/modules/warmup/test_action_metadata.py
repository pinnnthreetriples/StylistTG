from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS, WRITE_ACTION_TYPES
from app.modules.warmup.action_metadata import (
    TRAFFIC_HEAVY_ACTIONS,
    is_traffic_heavy,
    list_action_metadata,
)


def test_action_metadata_covers_supported_advanced_actions() -> None:
    metadata = list_action_metadata()

    assert [item.action_type for item in metadata] == list(SUPPORTED_ADVANCED_ACTIONS)
    assert {item.action_type for item in metadata if item.write_action} == set(WRITE_ACTION_TYPES)
    assert {item.action_type for item in metadata if item.traffic_heavy} == set(
        TRAFFIC_HEAVY_ACTIONS
    )


def test_traffic_heavy_predicate_marks_expected_actions() -> None:
    assert is_traffic_heavy("search_gif") is True
    assert is_traffic_heavy("feed_read") is False


def test_traffic_heavy_predicate_rejects_unknown_action() -> None:
    assert is_traffic_heavy("unknown_action") is False


def test_action_metadata_assigns_categories() -> None:
    by_action = {item.action_type: item for item in list_action_metadata()}

    assert by_action["search_gif"].category == "entertainment"
    assert by_action["watch_video"].category == "activity"
    assert by_action["saved_messages"].category == "social"
    assert by_action["emoji_status"].requires_premium is True
