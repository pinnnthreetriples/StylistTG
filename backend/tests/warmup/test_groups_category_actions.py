from __future__ import annotations

import random
from datetime import UTC, datetime

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import WarmupExecutionMode
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy
from tests.warmup.test_warmup_network_advanced import (
    _ProgrammableTdlibClient,
    _make_real_adapter,
    _ready_event,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def test_mock_adapter_groups_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=51)

    archived = adapter.execute_action(
        account_id="acc-1",
        action_type="archive_chat",
        context={"chat_id": -100_42, "temporary": True},
    )
    assert archived.is_ok
    assert archived.metadata["chat_id"] == -100_42
    assert archived.metadata["temporary"] is True
    assert archived.metadata["reversed"] is True

    muted = adapter.execute_action(
        account_id="acc-1",
        action_type="mute_chat",
        context={"chat_id": -100_43, "mute_for_seconds": 3600},
    )
    assert muted.is_ok
    assert muted.metadata["mute_for_seconds"] == 3600

    skipped = adapter.execute_action(
        account_id="acc-1",
        action_type="archive_chat",
        context={"chat_id": 777000},
    )
    assert skipped.status == "skipped"
    assert skipped.error_code == "protected_chat"


def test_real_adapter_archive_chat_uses_archive_list(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [777000, -100_42]},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(account_id="acc-1", action_type="archive_chat", context={})
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == ["getChats", "addChatToList"]
    assert client.queries[1]["chat_id"] == -100_42
    assert client.queries[1]["chat_list"] == {"@type": "chatListArchive"}
    assert result.metadata["archived"] is True


def test_real_adapter_archive_chat_reverses_when_temporary(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [-100_42]},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="archive_chat",
            context={"temporary": True},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getChats",
        "addChatToList",
        "addChatToList",
    ]
    assert client.queries[1]["chat_list"] == {"@type": "chatListArchive"}
    assert client.queries[2]["chat_list"] == {"@type": "chatListMain"}
    assert result.metadata["reversed"] is True


def test_real_adapter_mute_chat_sets_notification_settings(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [-100_43]},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="mute_chat",
            context={"temporary": True, "mute_for_seconds": 3600},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getChats",
        "setChatNotificationSettings",
        "setChatNotificationSettings",
    ]
    assert client.queries[1]["notification_settings"]["mute_for"] == 3600
    assert client.queries[2]["notification_settings"]["mute_for"] == 0
    assert result.metadata["mute_for_seconds"] == 3600
    assert result.metadata["reversed"] is True


def test_real_adapter_groups_actions_skip_protected_chat(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "chats", "chat_ids": [777000, 123]}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(account_id="acc-1", action_type="mute_chat", context={})
    finally:
        adapter.close()

    assert result.status == "skipped"
    assert result.error_code == "protected_chat"
    assert [query["@type"] for query in client.queries] == ["getChats"]


def test_shadow_groups_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[],
        daily_action_limits={"1": {"archive_chat": 1, "mute_chat": 1}},
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
    assert warmup_session.daily_counters_json.get("0", {}) == {
        "archive_chat": 1,
        "mute_chat": 1,
    }
