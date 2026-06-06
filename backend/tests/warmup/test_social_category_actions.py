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

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def test_mock_adapter_social_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=41)

    forward = adapter.execute_action(
        account_id="acc-1",
        action_type="forward_message",
        context={"channel_ref": "@news"},
    )
    assert forward.is_ok
    assert forward.metadata["to_chat"] == "saved_messages"

    saved = adapter.execute_action(
        account_id="acc-1",
        action_type="saved_messages",
        context={"note_text": "todo"},
    )
    assert saved.is_ok
    assert saved.metadata["text_length"] == 4

    skipped = adapter.execute_action(account_id="acc-1", action_type="sync_contacts", context={})
    assert skipped.status == "skipped"
    assert skipped.error_code == "no_contacts_pool_available"

    synced = adapter.execute_action(
        account_id="acc-1",
        action_type="sync_contacts",
        context={"contacts_pool": [{"phone_number": "+10000000000", "first_name": "A"}]},
    )
    assert synced.is_ok
    assert synced.metadata["contacts_imported"] == 1


def test_real_adapter_forward_message_to_saved_messages(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {"@type": "messages", "messages": [{"id": 9}]},
            {"@type": "user", "id": 123},
            {"@type": "chat", "id": 123},
            {"@type": "messages", "messages": [{"id": 90}]},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="forward_message",
            context={"channel_ref": "@news", "history_limit": 5},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchPublicChat",
        "getChatHistory",
        "getMe",
        "createPrivateChat",
        "forwardMessages",
    ]
    assert client.queries[4]["from_chat_id"] == -100_42
    assert client.queries[4]["chat_id"] == 123
    assert client.queries[4]["message_ids"] == [9]
    assert result.metadata["to_chat"] == "saved_messages"


def test_real_adapter_saved_messages_sends_note(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "user", "id": 123},
            {"@type": "chat", "id": 123},
            {"@type": "message", "id": 7},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="saved_messages",
            context={"note_text": "remember"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getMe",
        "createPrivateChat",
        "sendMessage",
    ]
    assert client.queries[2]["chat_id"] == 123
    assert client.queries[2]["input_message_content"]["text"]["text"] == "remember"
    assert result.metadata["text_length"] == len("remember")


def test_real_adapter_sync_contacts_skips_without_pool(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "users", "user_ids": [1, 2]}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="sync_contacts",
            context={},
        )
    finally:
        adapter.close()

    assert result.status == "skipped"
    assert result.error_code == "no_contacts_pool_available"
    assert client.queries == [{"@type": "getContacts"}]
    assert result.metadata["existing_contacts"] == 2


def test_real_adapter_sync_contacts_imports_pool(monkeypatch) -> None:
    contact = {"phone_number": "+10000000000", "first_name": "A", "last_name": ""}
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "users", "user_ids": []},
            {"@type": "importedContacts", "user_ids": [55]},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="sync_contacts",
            context={"contacts_pool": [contact]},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == ["getContacts", "importContacts"]
    assert client.queries[1]["contacts"] == [contact]
    assert result.metadata["contacts_imported"] == 1


def test_dispatch_sync_contacts_skips_without_pool(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.ADVANCED.value,
        target_channels=[],
        daily_action_limits={"1": {"sync_contacts": 1}},
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
    assert warmup_session.daily_counters_json.get("0", {}).get("sync_contacts", 0) == 0
    assert any(
        event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "no_contacts_pool_available"
        for event in warmup_session.events
    )


def test_shadow_social_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={
            "1": {
                "forward_message": 1,
                "saved_messages": 1,
                "sync_contacts": 1,
            }
        },
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
    for _ in range(5):
        process_due_warmup_dispatches(
            db_session,
            worker_id="w1",
            now=NOW,
            rng=rng,
            passive_adapter=adapter,
        )
        db_session.refresh(warmup_session)
        counters = warmup_session.daily_counters_json.get("0", {})
        if counters.get("sync_contacts") == 1:
            break
        warmup_session.next_micro_session_at = NOW
        db_session.commit()

    assert adapter.calls == []
    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters == {
        "forward_message": 1,
        "saved_messages": 1,
        "sync_contacts": 1,
    }
