"""Unit tests for testable parts of app.adapters.warmup_tdlib.

Covers: collect_supported_actions, MockWarmupTdlibAdapter,
UnavailableWarmupTdlibAdapter, _classify_tdlib_error, _AdapterClientError,
WarmupActionResult, and SUPPORTED_ACTIONS_BY_MODE constants.
"""

from __future__ import annotations

from app.adapters.warmup_tdlib import (
    SUPPORTED_ACTIONS_BY_MODE,
    SUPPORTED_ADVANCED_ACTIONS,
    SUPPORTED_PASSIVE_ACTIONS,
    WRITE_ACTION_TYPES,
    MockWarmupTdlibAdapter,
    UnavailableWarmupTdlibAdapter,
    WarmupActionResult,
    _AdapterClientError,
    _classify_tdlib_error,
    collect_supported_actions,
)


# ---------------------------------------------------------------------------
# collect_supported_actions
# ---------------------------------------------------------------------------


def test_collect_supported_actions_passive_only():
    result = collect_supported_actions(("passive",))
    assert result == set(SUPPORTED_PASSIVE_ACTIONS)


def test_collect_supported_actions_all_modes():
    result = collect_supported_actions(("passive", "network", "advanced"))
    assert "get_me" in result
    assert "channel_browse" in result
    assert "view_story" in result
    assert "join_chat" in result
    assert "react_to_post" in result
    assert "p2p_send" in result


def test_collect_supported_actions_empty():
    assert collect_supported_actions(()) == set()


def test_collect_supported_actions_unknown_mode():
    assert collect_supported_actions(("nonexistent",)) == set()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_supported_actions_by_mode_keys():
    assert set(SUPPORTED_ACTIONS_BY_MODE.keys()) == {"passive", "network", "advanced"}


def test_write_action_types():
    assert WRITE_ACTION_TYPES == frozenset(
        {
            "archive_chat",
            "drafts",
            "emoji_status",
            "forward_message",
            "join_chat",
            "mute_chat",
            "notification_settings",
            "p2p_send",
            "react_to_post",
            "saved_messages",
            "scheduled_messages",
            "simulate_typing",
            "sync_contacts",
            "update_profile_gradual",
        }
    )
    assert WRITE_ACTION_TYPES.issubset(set(SUPPORTED_ADVANCED_ACTIONS))


# ---------------------------------------------------------------------------
# WarmupActionResult
# ---------------------------------------------------------------------------


def test_action_result_is_ok():
    r = WarmupActionResult(status="ok", action_type="get_me")
    assert r.is_ok is True


def test_action_result_not_ok():
    r = WarmupActionResult(status="network_error", action_type="get_me")
    assert r.is_ok is False


def test_action_result_metadata_default():
    r = WarmupActionResult(status="ok", action_type="get_me")
    assert r.metadata == {}


# ---------------------------------------------------------------------------
# MockWarmupTdlibAdapter
# ---------------------------------------------------------------------------


def test_mock_adapter_is_available():
    adapter = MockWarmupTdlibAdapter()
    assert adapter.is_available() is True
    assert adapter.provider_name == "mock"


def test_mock_adapter_supports_all_by_default():
    adapter = MockWarmupTdlibAdapter()
    assert adapter.supports_action("get_me") is True
    assert adapter.supports_action("join_chat") is True
    assert adapter.supports_action("p2p_send") is True


def test_mock_adapter_passive_only():
    adapter = MockWarmupTdlibAdapter(supported_modes=("passive",))
    assert adapter.supports_action("get_me") is True
    assert adapter.supports_action("channel_browse") is True
    assert adapter.supports_action("view_story") is True
    assert adapter.supports_action("join_chat") is False
    assert adapter.supports_action("react_to_post") is False
    assert adapter.supports_action("p2p_send") is False


def test_mock_adapter_get_me():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(account_id="a1", action_type="get_me", context={})
    assert result.is_ok
    assert result.metadata["telegram_user_id_present"] is True
    assert len(adapter.calls) == 1


def test_mock_adapter_feed_read():
    adapter = MockWarmupTdlibAdapter(rng_seed=42)
    result = adapter.execute_action(account_id="a1", action_type="feed_read", context={})
    assert result.is_ok
    assert "chats_seen" in result.metadata
    assert "messages_viewed" in result.metadata


def test_mock_adapter_ping_proxy():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(
        account_id="a1", action_type="ping_proxy", context={"proxy_category": "residential"}
    )
    assert result.is_ok
    assert result.metadata["proxy_status"] == "reachable"
    assert result.metadata["proxy_category"] == "residential"


def test_mock_adapter_join_chat_ok():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(
        account_id="a1", action_type="join_chat", context={"chat_target": "@test_channel"}
    )
    assert result.is_ok
    assert result.metadata["chat_target"] == "@test_channel"
    assert "joined_chat_id" in result.metadata


def test_mock_adapter_join_chat_missing_target():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(account_id="a1", action_type="join_chat", context={})
    assert result.status == "missing_context"
    assert result.error_code == "join_chat_missing_target"


def test_mock_adapter_channel_browse_ok():
    adapter = MockWarmupTdlibAdapter(rng_seed=42)
    result = adapter.execute_action(
        account_id="a1",
        action_type="channel_browse",
        context={"channel_ref": "@news"},
    )
    assert result.is_ok
    assert result.metadata["channel_ref"] == "@news"
    assert result.metadata["messages_viewed"] <= result.metadata["messages_total"]


def test_mock_adapter_view_story_ok():
    adapter = MockWarmupTdlibAdapter(rng_seed=42)
    result = adapter.execute_action(
        account_id="a1",
        action_type="view_story",
        context={"channel_ref": "@news", "has_stories": True},
    )
    assert result.is_ok
    assert result.metadata["channel_ref"] == "@news"
    assert result.metadata["has_stories"] is True
    assert result.metadata["viewed_count"] >= 1


def test_mock_adapter_react_to_post_ok():
    adapter = MockWarmupTdlibAdapter(rng_seed=42)
    result = adapter.execute_action(
        account_id="a1",
        action_type="react_to_post",
        context={"channel_ref": "@news", "available_reactions": ["👍", "🔥"]},
    )
    assert result.is_ok
    assert result.metadata["channel_ref"] == "@news"
    assert result.metadata["reaction"] in {"👍", "🔥"}
    assert result.metadata["has_reactions"] is True


def test_mock_adapter_react_to_post_prefers_favorite_emoji():
    adapter = MockWarmupTdlibAdapter(rng_seed=1)
    result = adapter.execute_action(
        account_id="a1",
        action_type="react_to_post",
        context={
            "channel_ref": "@news",
            "available_reactions": ["👍", "🔥"],
            "personality_seed": {"favorite_emojis": ["🔥"]},
        },
    )

    assert result.is_ok
    assert result.metadata["reaction"] == "🔥"


def test_mock_adapter_p2p_send_ok():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(
        account_id="a1",
        action_type="p2p_send",
        context={"peer_account_id": "peer-1", "text": "hello", "text_seed": "s1"},
    )
    assert result.is_ok
    assert result.metadata["text_length"] == 5


def test_mock_adapter_p2p_send_missing_context():
    adapter = MockWarmupTdlibAdapter()
    result = adapter.execute_action(account_id="a1", action_type="p2p_send", context={})
    assert result.status == "missing_context"


def test_mock_adapter_unsupported_action():
    adapter = MockWarmupTdlibAdapter(supported_modes=("passive",))
    result = adapter.execute_action(account_id="a1", action_type="join_chat", context={})
    assert result.status == "unsupported"


def test_mock_adapter_forced_failure():
    adapter = MockWarmupTdlibAdapter(
        failure_action_types=("get_me",),
        failure_status="flood_wait",
        failure_retry_after_seconds=30,
    )
    result = adapter.execute_action(account_id="a1", action_type="get_me", context={})
    assert result.status == "flood_wait"
    assert result.retry_after_seconds == 30
    assert result.error_code == "mock_forced_failure"


def test_mock_adapter_close_is_noop():
    adapter = MockWarmupTdlibAdapter()
    adapter.close()  # should not raise
    # Verify adapter remains usable after close
    result = adapter.execute_action(account_id="a1", action_type="get_me", context={})
    assert result.status == "ok"


def test_mock_adapter_deterministic_with_seed():
    a = MockWarmupTdlibAdapter(rng_seed=42)
    b = MockWarmupTdlibAdapter(rng_seed=42)
    r1 = a.execute_action(account_id="a", action_type="feed_read", context={})
    r2 = b.execute_action(account_id="a", action_type="feed_read", context={})
    assert r1.metadata == r2.metadata


# ---------------------------------------------------------------------------
# UnavailableWarmupTdlibAdapter
# ---------------------------------------------------------------------------


def test_unavailable_adapter_not_available():
    adapter = UnavailableWarmupTdlibAdapter("all disabled")
    assert adapter.is_available() is False
    assert adapter.provider_name == "unavailable"


def test_unavailable_adapter_supports_nothing():
    adapter = UnavailableWarmupTdlibAdapter("disabled")
    assert adapter.supports_action("get_me") is False
    assert adapter.supports_action("join_chat") is False


def test_unavailable_adapter_execute():
    adapter = UnavailableWarmupTdlibAdapter("config_off")
    result = adapter.execute_action(account_id="a1", action_type="get_me", context={})
    assert result.status == "unavailable"
    assert result.metadata["reason"] == "config_off"


def test_unavailable_adapter_close():
    adapter = UnavailableWarmupTdlibAdapter("off")
    adapter.close()  # should not raise
    # Verify adapter still reports unavailable after close
    assert adapter.is_available() is False


# ---------------------------------------------------------------------------
# _classify_tdlib_error
# ---------------------------------------------------------------------------


def test_classify_tdlib_error_flood_wait():
    error = {"message": "FLOOD_WAIT_120"}
    result = _classify_tdlib_error(error, "get_me")
    assert result.status == "flood_wait"
    assert result.retry_after_seconds == 120
    assert result.error_code == "tdlib_flood_wait"


def test_classify_tdlib_error_frozen():
    error = {"message": "USER_DEACTIVATED_BAN"}
    result = _classify_tdlib_error(error, "feed_read")
    assert result.status == "runtime_broken"
    assert result.error_class == "runtime"


def test_classify_tdlib_error_deactivated():
    error = {"message": "AUTH_KEY_UNREGISTERED"}
    result = _classify_tdlib_error(error, "get_me")
    assert result.status == "runtime_broken"


def test_classify_tdlib_error_generic():
    error = {"message": "CHAT_NOT_FOUND"}
    result = _classify_tdlib_error(error, "join_chat")
    assert result.status == "network_error"
    assert result.error_code == "tdlib_error"


def test_classify_tdlib_error_empty_message():
    result = _classify_tdlib_error({}, "get_me")
    assert result.status == "network_error"


# ---------------------------------------------------------------------------
# _AdapterClientError
# ---------------------------------------------------------------------------


def test_adapter_client_error_as_action_result():
    err = _AdapterClientError(
        status="runtime_broken",
        error_code="tdlib_auth_error",
        error_class="auth_state",
        message="auth failed",
    )
    result = err.as_action_result("get_me")
    assert result.status == "runtime_broken"
    assert result.action_type == "get_me"
    assert result.error_code == "tdlib_auth_error"
    assert result.metadata["message"] == "auth failed"


def test_adapter_client_error_from_tdlib_flood():
    err = _AdapterClientError.from_tdlib_error({"message": "FLOOD_WAIT_30"})
    assert err.status == "flood_wait"
    assert err.error_code == "tdlib_flood_wait"


def test_adapter_client_error_from_tdlib_generic():
    err = _AdapterClientError.from_tdlib_error({"message": "some_tdlib_error"})
    assert err.status == "runtime_broken"
    assert err.error_code == "tdlib_auth_error"
