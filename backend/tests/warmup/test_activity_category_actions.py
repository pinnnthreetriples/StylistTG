from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

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

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def test_mock_adapter_supports_activity_category_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=21)

    missing = adapter.execute_action(account_id="acc-1", action_type="vote_poll", context={})
    assert missing.status == "missing_context"

    skipped = adapter.execute_action(
        account_id="acc-1",
        action_type="watch_video",
        context={"channel_ref": "@news", "has_video": False},
    )
    assert skipped.status == "skipped"
    assert skipped.error_code == "no_video_found"
    assert skipped.metadata["traffic_heavy"] is True

    for action_type in ("vote_poll", "watch_video", "listen_voice"):
        result = adapter.execute_action(
            account_id="acc-1",
            action_type=action_type,
            context={"channel_ref": "@news"},
        )
        assert result.is_ok
        assert result.metadata["channel_ref"] == "@news"
        if action_type in {"watch_video", "listen_voice"}:
            assert result.metadata["traffic_heavy"] is True


def test_real_adapter_vote_poll_uses_poll_answer(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {
                "@type": "messages",
                "messages": [
                    {
                        "id": 10,
                        "content": {
                            "@type": "messagePoll",
                            "poll": {
                                "is_closed": False,
                                "options": [{"id": "a"}, {"id": "b"}],
                            },
                        },
                    }
                ],
            },
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="vote_poll",
            context={"channel_ref": "@news", "history_limit": 15},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchPublicChat",
        "getChatHistory",
        "setPollAnswer",
    ]
    assert client.queries[2]["chat_id"] == -100_42
    assert client.queries[2]["message_id"] == 10
    assert client.queries[2]["option_ids"] == ["a"]
    assert result.metadata["chosen_option"] == "a"
    assert result.metadata["safety_hint"] == "avoid_empty_or_new_accounts"


@pytest.mark.parametrize(
    ("action_type", "message_id", "content", "file_id"),
    [
        (
            "watch_video",
            20,
            {
                "@type": "messageVideo",
                "video": {"video": {"id": 777}},
            },
            777,
        ),
        (
            "listen_voice",
            30,
            {
                "@type": "messageVoiceNote",
                "voice_note": {"voice": {"id": 888}},
            },
            888,
        ),
    ],
)
def test_real_adapter_activity_media_gets_file_and_opens_content(
    monkeypatch, action_type: str, message_id: int, content: dict[str, object], file_id: int
) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {
                "@type": "messages",
                "messages": [
                    {
                        "id": message_id,
                        "content": content,
                    }
                ],
            },
            {"@type": "file", "id": file_id},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type=action_type,
            context={"channel_ref": "@news"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchPublicChat",
        "getChatHistory",
        "getFile",
        "openMessageContent",
    ]
    assert client.queries[2]["file_id"] == file_id
    assert client.queries[3]["message_id"] == message_id
    assert result.metadata["traffic_heavy"] is True


def test_dispatch_records_skip_when_adapter_finds_no_poll(db_session, monkeypatch) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"vote_poll": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    channel_state_repository.upsert_subscribed(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        now=NOW,
    )
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {"@type": "messages", "messages": []},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    assert [query["@type"] for query in client.queries] == ["searchPublicChat", "getChatHistory"]
    assert warmup_session.daily_counters_json.get("0", {}).get("vote_poll", 0) == 0
    assert any(
        event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "no_open_poll_found"
        for event in warmup_session.events
    )


def test_shadow_activity_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={
            "1": {
                "vote_poll": 1,
                "watch_video": 1,
                "listen_voice": 1,
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
        "vote_poll": 1,
        "watch_video": 1,
        "listen_voice": 1,
    }
