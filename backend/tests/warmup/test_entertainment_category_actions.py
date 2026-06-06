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

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def test_mock_adapter_entertainment_actions_are_traffic_heavy() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=31)

    for action_type in ("search_gif", "view_stickers", "inline_bot", "link_preview"):
        result = adapter.execute_action(account_id="acc-1", action_type=action_type, context={})
        assert result.is_ok
        assert result.metadata["traffic_heavy"] is True

    skipped = adapter.execute_action(
        account_id="acc-1",
        action_type="inline_bot",
        context={"inline_bot_username": "@unknown"},
    )
    assert skipped.status == "skipped"
    assert skipped.error_code == "inline_bot_not_approved"


def test_real_adapter_search_gif_searches_animations_and_gets_top_files(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {
                "@type": "animations",
                "animations": [
                    {"animation": {"id": 101}},
                    {"animation": {"animation": {"id": 102}}},
                    {"file_id": 103},
                    {"file_id": 104},
                ],
            },
            {"@type": "file", "id": 101},
            {"@type": "file", "id": 102},
            {"@type": "file", "id": 103},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="search_gif",
            context={"search_query": "party"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchAnimations",
        "getFile",
        "getFile",
        "getFile",
    ]
    assert client.queries[0]["query"] == "party"
    assert [query["file_id"] for query in client.queries[1:]] == [101, 102, 103]
    assert result.metadata["traffic_heavy"] is True
    assert result.metadata["files_touched"] == 3


def test_real_adapter_view_stickers_reads_recent_sets(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {
                "@type": "stickers",
                "stickers": [{"set_id": 11}, {"set_id": 12}, {"set_id": 11}],
            },
            {"@type": "stickerSet", "id": 11},
            {"@type": "stickerSet", "id": 12},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="view_stickers",
            context={},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "getRecentStickers",
        "getStickerSet",
        "getStickerSet",
    ]
    assert [query["set_id"] for query in client.queries[1:]] == [11, 12]
    assert result.metadata["traffic_heavy"] is True
    assert result.metadata["sets_viewed"] == 2


def test_real_adapter_inline_bot_queries_only_approved_bot(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": 555},
            {"@type": "inlineQueryResults", "results": [{"id": "a"}, {"id": "b"}]},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="inline_bot",
            context={"inline_bot_username": "@gif", "inline_query": "cat", "inline_chat_id": 0},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "searchPublicChat",
        "getInlineQueryResults",
    ]
    assert client.queries[0]["username"] == "gif"
    assert client.queries[1]["bot_user_id"] == 555
    assert client.queries[1]["query"] == "cat"
    assert result.metadata["traffic_heavy"] is True
    assert result.metadata["results_seen"] == 2


def test_real_adapter_inline_bot_rejects_unapproved_bot(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(receive_queue=[_ready_event()])
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="inline_bot",
            context={"inline_bot_username": "@random_user_bot"},
        )
    finally:
        adapter.close()

    assert result.status == "skipped"
    assert result.error_code == "inline_bot_not_approved"
    assert client.queries == []
    assert result.metadata["traffic_heavy"] is True


def test_real_adapter_link_preview_uses_safe_url(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "webPage", "url": "https://example.com/"}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="link_preview",
            context={"preview_url": "https://example.com/"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries == [{"@type": "getWebPagePreview", "text": "https://example.com/"}]
    assert result.metadata["traffic_heavy"] is True


def test_shadow_entertainment_actions_do_not_call_adapter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[],
        daily_action_limits={
            "1": {
                "search_gif": 1,
                "view_stickers": 1,
                "inline_bot": 1,
                "link_preview": 1,
            }
        },
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    adapter = MockWarmupTdlibAdapter()

    _drive_shadow_until_complete(db_session, warmup_session, adapter)

    assert adapter.calls == []
    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters == {
        "search_gif": 1,
        "view_stickers": 1,
        "inline_bot": 1,
        "link_preview": 1,
    }


def _drive_shadow_until_complete(db_session, warmup_session, adapter) -> None:
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
        if all(
            counters.get(action_type) == 1
            for action_type in ("search_gif", "view_stickers", "inline_bot", "link_preview")
        ):
            return
        warmup_session.next_micro_session_at = NOW
        db_session.commit()
    raise AssertionError("shadow entertainment actions did not complete")
