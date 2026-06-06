from __future__ import annotations

import random
from datetime import UTC, datetime

from sqlalchemy import select

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import WarmupChannelState, WarmupExecutionMode
from app.modules.warmup.channel_state import repository as channel_state_repository
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy
from tests.warmup.test_warmup_network_advanced import (
    _ProgrammableTdlibClient,
    _make_real_adapter,
    _ready_event,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def test_mock_adapter_supports_reading_category_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=11)

    for action_type in ("view_dialogs", "mark_as_read", "search_messages"):
        result = adapter.execute_action(account_id="acc-1", action_type=action_type, context={})
        assert result.is_ok
        assert result.metadata["provider"] == "mock"

    missing = adapter.execute_action(
        account_id="acc-1",
        action_type="scroll_channels",
        context={},
    )
    assert missing.status == "missing_context"
    assert missing.error_code == "scroll_channels_missing_channel"

    ok = adapter.execute_action(
        account_id="acc-1",
        action_type="scroll_channels",
        context={"channel_ref": "@news", "history_limit": 25},
    )
    assert ok.is_ok
    assert ok.metadata["channel_ref"] == "@news"
    assert ok.metadata["messages_viewed"] > 0


def test_real_adapter_view_dialogs_reads_three_to_five_dialogs(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [1, 2, 3, 4, 5, 6]},
            {"@type": "ok"},
            {"@type": "ok"},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="view_dialogs",
            context={"dialog_limit": 4},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getChats",
        "viewMessages",
        "viewMessages",
        "viewMessages",
        "viewMessages",
    ]
    assert client.queries[0]["limit"] == 4
    assert result.metadata["chats_seen"] == 4
    assert result.metadata["messages_viewed"] == 4


def test_real_adapter_scroll_channels_uses_history_and_multiple_views(monkeypatch) -> None:
    messages = [{"id": index} for index in range(1, 23)]
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {"@type": "ok"},
            {"@type": "messages", "messages": messages},
            {"@type": "ok"},
            {"@type": "ok"},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="scroll_channels",
            context={"channel_ref": "@news", "history_limit": 22},
        )
    finally:
        adapter.close()

    assert result.is_ok
    types = [query["@type"] for query in client.queries]
    assert types == [
        "searchPublicChat",
        "openChat",
        "getChatHistory",
        "viewMessages",
        "viewMessages",
        "viewMessages",
        "closeChat",
    ]
    assert client.queries[2]["limit"] == 22
    assert client.queries[3]["message_ids"] == list(range(1, 11))
    assert client.queries[4]["message_ids"] == list(range(11, 21))
    assert client.queries[5]["message_ids"] == [21, 22]
    assert result.metadata["messages_viewed"] == 22


def test_real_adapter_mark_as_read_marks_dialogs(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [1, 2, 3]},
            {"@type": "ok"},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="mark_as_read",
            context={"dialog_limit": 3},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getChats",
        "viewMessages",
        "viewMessages",
        "viewMessages",
    ]
    assert result.metadata["chats_marked"] == 3


def test_real_adapter_search_messages_uses_global_search(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "messages", "messages": [{"id": 7}, {"id": 8}]},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="search_messages",
            context={"search_query": "news", "search_limit": 9},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries[0] == {
        "@type": "searchMessages",
        "chat_list": {"@type": "chatListMain"},
        "query": "news",
        "offset": "",
        "limit": 9,
        "filter": {"@type": "searchMessagesFilterEmpty"},
        "min_date": 0,
        "max_date": 0,
    }
    assert result.metadata["results_seen"] == 2


def test_dispatch_scroll_channels_requires_subscribed_channel_and_records_state(
    db_session,
) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"scroll_channels": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    channel_state_repository.upsert_subscribed(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        now=NOW,
    )
    adapter = MockWarmupTdlibAdapter(rng_seed=12)

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    calls = [call for call in adapter.calls if call["action_type"] == "scroll_channels"]
    assert len(calls) == 1
    assert calls[0]["context"]["channel_ref"] == "@news"
    state = db_session.execute(select(WarmupChannelState)).scalar_one()
    assert state.last_browse_at is not None
    assert warmup_session.daily_counters_json.get("0", {}).get("scroll_channels") == 1


def test_dispatch_scroll_channels_skips_without_channel_context(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"scroll_channels": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    adapter = MockWarmupTdlibAdapter()

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    assert [call for call in adapter.calls if call["action_type"] == "scroll_channels"] == []
    assert any(
        event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "no_scroll_channel_available"
        for event in warmup_session.events
    )


def test_shadow_reading_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={
            "1": {
                "view_dialogs": 1,
                "mark_as_read": 1,
                "search_messages": 1,
            }
        },
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    adapter = MockWarmupTdlibAdapter()

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    assert adapter.calls == []
    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters == {
        "view_dialogs": 1,
        "mark_as_read": 1,
        "search_messages": 1,
    }
