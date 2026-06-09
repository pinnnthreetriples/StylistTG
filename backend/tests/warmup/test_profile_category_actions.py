from __future__ import annotations

import random
from datetime import UTC, datetime

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import WarmupExecutionMode
from app.modules.warmup.channel_state import repository as channel_state_repository
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy
from tests.warmup.test_warmup_network_advanced import (
    _ProgrammableTdlibClient,
    _make_real_adapter,
    _ready_event,
)

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
PROFILE_ACTIONS = (
    "simulate_typing",
    "view_profile",
    "check_settings",
    "emoji_status",
    "drafts",
    "scheduled_messages",
    "update_profile_gradual",
    "notification_settings",
)


def test_mock_adapter_profile_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=61)

    for action_type in PROFILE_ACTIONS:
        context = {"chat_id": -100_42, "is_premium": True}
        result = adapter.execute_action(
            account_id="acc-1", action_type=action_type, context=context
        )
        assert result.is_ok
        assert result.metadata["provider"] == "mock"

    skipped = adapter.execute_action(
        account_id="acc-1",
        action_type="emoji_status",
        context={"is_premium": False},
    )
    assert skipped.status == "skipped"
    assert skipped.error_code == "non_premium_account"


def test_real_adapter_simulate_typing_uses_send_chat_action(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "chat", "id": -100_42}, {"@type": "ok"}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="simulate_typing",
            context={"channel_ref": "@news", "typing_duration_seconds": 6},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == ["searchPublicChat", "sendChatAction"]
    assert client.queries[1]["action"] == {"@type": "chatActionTyping"}
    assert result.metadata["typing_duration_seconds"] == 6


def test_real_adapter_view_profile_uses_contacts_user(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "users", "user_ids": [99]}, {"@type": "user", "id": 99}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(account_id="acc-1", action_type="view_profile", context={})
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == ["getContacts", "getUser"]
    assert client.queries[1]["user_id"] == 99


def test_real_adapter_check_settings_uses_get_option(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "optionValueInteger", "value": 10}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="check_settings",
            context={"option_name": "notification_group_count_max"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries == [{"@type": "getOption", "name": "notification_group_count_max"}]


def test_real_adapter_emoji_status_skips_non_premium(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(receive_queue=[_ready_event()])
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="emoji_status",
            context={"is_premium": False},
        )
    finally:
        adapter.close()

    assert result.status == "skipped"
    assert result.error_code == "non_premium_account"
    assert client.queries == []


def test_real_adapter_drafts_sets_and_clears(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "chat", "id": -100_42}, {"@type": "ok"}, {"@type": "ok"}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="drafts",
            context={"channel_ref": "@news", "draft_text": "todo", "temporary": True},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchPublicChat",
        "setChatDraftMessage",
        "setChatDraftMessage",
    ]
    assert client.queries[1]["draft_message"]["input_message_text"]["text"]["text"] == "todo"
    assert client.queries[2]["draft_message"] is None
    assert result.metadata["cleared"] is True


def test_real_adapter_scheduled_messages_schedules_and_edits(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "user", "id": 123},
            {"@type": "chat", "id": 123},
            {"@type": "message", "id": 55},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="scheduled_messages",
            context={"note_text": "remember", "schedule_at": 1_800_000_100, "temporary": True},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getMe",
        "createPrivateChat",
        "sendMessage",
        "editMessageSchedulingState",
    ]
    assert client.queries[2]["scheduling_state"]["send_date"] == 1_800_000_100
    assert client.queries[3]["scheduling_state"] is None


def test_real_adapter_update_profile_gradual_updates_one_field(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(receive_queue=[_ready_event()], responses=[{"@type": "ok"}])
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="update_profile_gradual",
            context={"profile_field": "bio", "bio": "reading"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries == [{"@type": "setBio", "bio": "reading"}]
    assert result.metadata["profile_field"] == "bio"


def test_real_adapter_notification_settings_sets_scope(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(receive_queue=[_ready_event()], responses=[{"@type": "ok"}])
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="notification_settings",
            context={"notification_scope": "channel", "mute_for_seconds": 600},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries[0]["@type"] == "setScopeNotificationSettings"
    assert client.queries[0]["scope"] == {"@type": "notificationSettingsScopeChannelChats"}
    assert client.queries[0]["notification_settings"]["mute_for"] == 600


def test_shadow_profile_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {action_type: 1 for action_type in PROFILE_ACTIONS}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    channel_state_repository.upsert_subscribed(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        now=NOW,
    )
    adapter = MockWarmupTdlibAdapter()
    rng = random.Random(0)

    for _ in range(10):
        process_due_warmup_dispatches(
            db_session,
            worker_id="w1",
            now=NOW,
            rng=rng,
            passive_adapter=adapter,
        )
        db_session.refresh(warmup_session)
        counters = warmup_session.daily_counters_json.get("0", {})
        if all(counters.get(action_type) == 1 for action_type in PROFILE_ACTIONS):
            break
        warmup_session.next_micro_session_at = NOW
        db_session.commit()

    assert adapter.calls == []
    counters = warmup_session.daily_counters_json.get("0", {})
    assert all(counters.get(action_type) == 1 for action_type in PROFILE_ACTIONS)
