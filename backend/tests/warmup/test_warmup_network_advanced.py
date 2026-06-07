"""Phase 3 + Phase 4 backend tests.

Покрывает:
- MockWarmupTdlibAdapter поддержка `join_chat` и `p2p_send` с context-валидацией.
- RealWarmupTdlibAdapter формирует корректные TDLib-команды через
  ProgrammableTdlibClient (без реального TDLib): getMe, getChats+viewMessages,
  searchPublicChat+joinChat, createPrivateChat+sendMessage, FLOOD_WAIT_X mapping.
- Dispatch network mode: prepare chat_target из strategy.target_channels_json,
  call adapter, increment counter, write session_action_executed.
- Dispatch advanced mode: подбор eligible peer, генерация текста, запись
  p2p_contact_recorded, mutual increment current_contacts.
- Dispatch skip-events: no_target_channels_configured, no_eligible_trusted_peers,
  text_provider_unavailable.
- Adapter cleanup: close() вызывается после dispatch tick.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.adapters.tdlib_auth import TdlibClient
from app.adapters.warmup_tdlib import (
    MockWarmupTdlibAdapter,
    RealWarmupTdlibAdapter,
    UnavailableWarmupTdlibAdapter,
    build_warmup_tdlib_adapter,
    collect_supported_actions,
)
from app.config import Settings, settings
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupExecutionMode,
    WarmupSession,
    WarmupTrustedPeer,
    new_id,
)
from app.services.warmup_dispatch import process_due_warmup_dispatches
from app.services.warmup_p2p import record_p2p_contact, select_eligible_peer
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session, seed_warmup_strategy


# ---------------------------------------------------------------------------
# Mock adapter contract (Phase 3 + 4)
# ---------------------------------------------------------------------------


def test_mock_adapter_join_chat_requires_chat_target() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=1)

    missing = adapter.execute_action(account_id="acc-1", action_type="join_chat", context={})
    assert missing.status == "missing_context"
    assert missing.error_code == "join_chat_missing_target"

    ok = adapter.execute_action(
        account_id="acc-1",
        action_type="join_chat",
        context={"chat_target": "@cool_news"},
    )
    assert ok.is_ok
    assert ok.metadata["chat_target"] == "@cool_news"
    assert "joined_chat_id" in ok.metadata


def test_mock_adapter_p2p_send_requires_peer_and_text() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=2)

    missing = adapter.execute_action(
        account_id="acc-1", action_type="p2p_send", context={"peer_account_id": "peer-1"}
    )
    assert missing.status == "missing_context"

    ok = adapter.execute_action(
        account_id="acc-1",
        action_type="p2p_send",
        context={
            "peer_account_id": "peer-1",
            "text": "hello",
            "text_seed": "abc",
        },
    )
    assert ok.is_ok
    assert ok.metadata["peer_account_id"] == "peer-1"
    assert ok.metadata["text_length"] == len("hello")
    assert ok.metadata["typing_started"] is True
    assert 2_000 <= ok.metadata["typing_duration_ms"] <= 15_000


def test_mock_adapter_supports_action_per_mode() -> None:
    passive_only = MockWarmupTdlibAdapter(supported_modes=("passive",))
    network = MockWarmupTdlibAdapter(supported_modes=("passive", "network"))
    advanced = MockWarmupTdlibAdapter(supported_modes=("passive", "network", "advanced"))

    assert passive_only.supports_action("feed_read")
    assert passive_only.supports_action("channel_browse")
    assert passive_only.supports_action("view_story")
    assert not passive_only.supports_action("join_chat")
    assert not passive_only.supports_action("react_to_post")
    assert not passive_only.supports_action("p2p_send")

    assert network.supports_action("join_chat")
    assert not network.supports_action("react_to_post")
    assert not network.supports_action("p2p_send")

    assert advanced.supports_action("react_to_post")
    assert advanced.supports_action("p2p_send")


def test_collect_supported_actions_progressive_layering() -> None:
    assert "feed_read" in collect_supported_actions(("passive",))
    assert "channel_browse" in collect_supported_actions(("passive",))
    assert "view_story" in collect_supported_actions(("passive",))
    assert "join_chat" not in collect_supported_actions(("passive",))
    assert "join_chat" in collect_supported_actions(("network",))
    assert "react_to_post" in collect_supported_actions(("advanced",))
    assert "p2p_send" in collect_supported_actions(("advanced",))


def test_factory_returns_unavailable_when_all_live_flags_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "warmup_passive_enabled", False)
    monkeypatch.setattr(settings, "warmup_network_enabled", False)
    monkeypatch.setattr(settings, "warmup_advanced_enabled", False)
    assert isinstance(build_warmup_tdlib_adapter(), UnavailableWarmupTdlibAdapter)


def test_real_adapter_reports_unavailable_without_tdlib_credentials(monkeypatch) -> None:
    """is_available()==False без api_id/api_hash → dispatch напишет task_skipped."""
    monkeypatch.setattr(settings, "warmup_network_enabled", True)
    monkeypatch.setattr(settings, "tdlib_api_id", 0)
    monkeypatch.setattr(settings, "tdlib_api_hash", "")
    adapter = build_warmup_tdlib_adapter()
    try:
        assert adapter.is_available() is False
    finally:
        adapter.close()


# ---------------------------------------------------------------------------
# Real adapter command shapes via ProgrammableTdlibClient
# ---------------------------------------------------------------------------


class _ProgrammableTdlibClient:
    """In-memory TdlibClient stub recording every send_query and replaying scripted responses.

    Контракт: каждый вызов `send_query(query, _)` сравнивается с next entry в
    `responses`. Если очередь пустая — возвращаем пустой dict (адаптер
    должен корректно среагировать как на error).
    """

    def __init__(
        self,
        *,
        receive_queue: list[dict[str, Any]] | None = None,
        responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self._receive = list(receive_queue or [])
        self._responses = list(responses or [])
        self.queries: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    @property
    def client_id(self) -> int:
        return 1

    def send(self, query: dict) -> None:
        self.sent.append(query)

    def receive(self, timeout_seconds: float) -> dict | None:
        del timeout_seconds
        if not self._receive:
            return None
        return self._receive.pop(0)

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        del timeout_seconds
        self.queries.append(query)
        if self._responses:
            return self._responses.pop(0)
        return {"@type": "error", "code": 500, "message": "no_response_scripted"}

    def close(self) -> None:
        self.closed = True


class _ScriptedFactory:
    """TdlibClientFactory returning a single pre-built ProgrammableTdlibClient."""

    def __init__(self, client: _ProgrammableTdlibClient) -> None:
        self._client = client
        self.created_for: list[str] = []

    def create(self, account_id: str) -> TdlibClient:
        self.created_for.append(account_id)
        return self._client  # type: ignore[return-value]


def _ready_event() -> dict[str, Any]:
    return {
        "@type": "updateAuthorizationState",
        "authorization_state": {"@type": "authorizationStateReady"},
    }


@contextmanager
def _real_adapter_session(
    monkeypatch,
    *,
    receive_queue: list,
    responses: list,
):
    """Build a RealWarmupTdlibAdapter over a scripted client and close on exit."""
    client = _ProgrammableTdlibClient(receive_queue=receive_queue, responses=responses)
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        yield client, adapter
    finally:
        adapter.close()


def _make_real_adapter(client: _ProgrammableTdlibClient, monkeypatch) -> RealWarmupTdlibAdapter:
    """Сборка RealWarmupTdlibAdapter поверх scripted client.

    `monkeypatch` оставлен в сигнатуре для тестов, но adapter получает
    отдельный Settings object, чтобы TDLib credentials не утекали в другие
    тесты через глобальный `settings`.
    """
    del monkeypatch
    factory = _ScriptedFactory(client)
    config = Settings(tdlib_api_id=1, tdlib_api_hash="test")
    return RealWarmupTdlibAdapter(client_factory=factory, config=config)


def test_real_adapter_get_me_emits_getMe_query(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[{"@type": "user", "id": 42, "username": "neo"}],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(account_id="acc-1", action_type="get_me", context={})
    finally:
        adapter.close()

    assert result.is_ok
    assert any(q["@type"] == "getMe" for q in client.queries)
    assert client.closed is True


def test_real_adapter_feed_read_uses_getChats_then_viewMessages(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chats", "chat_ids": [-100_1, -100_2]},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(account_id="acc-1", action_type="feed_read", context={})
    finally:
        adapter.close()

    assert result.is_ok
    types = [q["@type"] for q in client.queries]
    assert "getChats" in types
    assert types.count("viewMessages") == 2
    assert result.metadata["chats_seen"] == 2
    assert result.metadata["messages_viewed"] == 2


def test_real_adapter_join_chat_uses_searchPublicChat_then_joinChat(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42, "title": "Cool News"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="join_chat",
            context={"chat_target": "@cool_news"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert client.queries[0]["@type"] == "searchPublicChat"
    assert client.queries[0]["username"] == "cool_news"
    assert client.queries[1]["@type"] == "joinChat"
    assert client.queries[1]["chat_id"] == -100_42
    assert result.metadata["joined_chat_id"] == -100_42


def test_real_adapter_p2p_send_uses_typing_before_sendMessage(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": 555, "type": {"@type": "chatTypePrivate"}},
            {"@type": "ok"},
            {"@type": "message", "id": 7},
        ],
    )
    slept: list[float] = []
    monkeypatch.setattr("app.adapters.warmup_tdlib_real.time.sleep", slept.append)
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="p2p_send",
            context={
                "peer_telegram_user_id": "12345",
                "peer_account_id": "peer-row-1",
                "text": "Привет!",
                "text_seed": "deadbeef",
                "personality_seed": {"typing_speed_cps": 7},
            },
        )
    finally:
        adapter.close()

    assert result.is_ok
    _assert_p2p_typing_flow(client.queries, text="Привет!")
    assert slept == [result.metadata["typing_duration_ms"] / 1000]
    assert {
        "chat_id": result.metadata["chat_id"],
        "text_length": result.metadata["text_length"],
    } == {"chat_id": 555, "text_length": len("Привет!")}
    assert result.metadata["typing_started"] is True
    assert 2_000 <= result.metadata["typing_duration_ms"] <= 15_000


def _assert_p2p_typing_flow(queries: list[dict[str, object]], *, text: str) -> None:
    assert queries[0]["@type"] == "createPrivateChat"
    assert queries[0]["user_id"] == 12345
    assert queries[1]["@type"] == "sendChatAction"
    assert queries[1]["chat_id"] == 555
    assert isinstance(queries[1]["action"], dict)
    assert queries[1]["action"]["@type"] == "chatActionTyping"
    assert queries[2]["@type"] == "sendMessage"
    assert queries[2]["chat_id"] == 555
    assert isinstance(queries[2]["input_message_content"], dict)
    assert queries[2]["input_message_content"]["text"]["text"] == text


def test_real_adapter_p2p_send_continues_when_typing_fails(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": 555, "type": {"@type": "chatTypePrivate"}},
            {"@type": "error", "code": 500, "message": "typing_failed"},
            {"@type": "message", "id": 7},
        ],
    )
    monkeypatch.setattr("app.adapters.warmup_tdlib_real.time.sleep", lambda _: None)
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="p2p_send",
            context={
                "peer_telegram_user_id": "12345",
                "peer_account_id": "peer-row-1",
                "text": "hello",
                "text_seed": "deadbeef",
            },
        )
    finally:
        adapter.close()

    assert result.is_ok
    assert [query["@type"] for query in client.queries] == [
        "createPrivateChat",
        "sendChatAction",
        "sendMessage",
    ]
    assert result.metadata["typing_started"] is False
    assert result.metadata["typing_error_code"] == "typing_failed"


def test_real_adapter_channel_browse_uses_public_chat_history_flow(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42, "title": "Cool News"},
            {"@type": "ok"},
            {"@type": "messages", "messages": [{"id": 10}, {"id": 11}]},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="channel_browse",
            context={"channel_ref": "@cool_news", "history_limit": 12},
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
        "closeChat",
    ]
    assert client.queries[2]["limit"] == 12
    assert client.queries[3]["message_ids"] == [10, 11]
    assert result.metadata["messages_viewed"] == 2


def test_real_adapter_view_story_opens_active_stories(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {"@type": "chatActiveStories", "stories": [{"id": 1}, {"id": 2}]},
            {"@type": "ok"},
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="view_story",
            context={"channel_ref": "@cool_news"},
        )
    finally:
        adapter.close()

    assert result.is_ok
    types = [query["@type"] for query in client.queries]
    assert types == ["searchPublicChat", "getChatActiveStories", "openStory", "openStory"]
    assert result.metadata["viewed_count"] == 2
    assert result.metadata["has_stories"] is True


def test_real_adapter_react_to_post_uses_available_reaction(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "chat", "id": -100_42},
            {"@type": "messages", "messages": [{"id": 10}, {"id": 11}]},
            {
                "@type": "availableReactions",
                "reactions": [{"type": {"@type": "reactionTypeEmoji", "emoji": "👍"}}],
            },
            {"@type": "ok"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    try:
        result = adapter.execute_action(
            account_id="acc-1",
            action_type="react_to_post",
            context={"channel_ref": "@cool_news", "available_reactions": ["🔥"]},
        )
    finally:
        adapter.close()

    assert result.is_ok
    types = [query["@type"] for query in client.queries]
    assert types == [
        "searchPublicChat",
        "getChatHistory",
        "getMessageAvailableReactions",
        "addMessageReaction",
    ]
    assert client.queries[3]["message_id"] == 10
    assert client.queries[3]["reaction_type"] == {
        "@type": "reactionTypeEmoji",
        "emoji": "👍",
    }
    assert client.queries[3]["is_big"] is False
    assert result.metadata["reaction"] == "👍"


def test_real_adapter_maps_flood_wait_with_retry_after(monkeypatch) -> None:
    with _real_adapter_session(
        monkeypatch,
        receive_queue=[_ready_event()],
        responses=[{"@type": "error", "code": 429, "message": "FLOOD_WAIT_30"}],
    ) as (_client, adapter):
        result = adapter.execute_action(account_id="acc-1", action_type="get_me", context={})

    assert result.status == "flood_wait"
    assert result.retry_after_seconds == 30
    assert result.error_code == "tdlib_flood_wait"


def test_real_adapter_close_idempotent_and_drops_clients(monkeypatch) -> None:
    client = _ProgrammableTdlibClient(
        receive_queue=[_ready_event()],
        responses=[
            {"@type": "user", "id": 1, "username": "u"},
        ],
    )
    adapter = _make_real_adapter(client, monkeypatch)
    adapter.execute_action(account_id="acc-1", action_type="get_me", context={})
    assert client.closed is False
    adapter.close()
    assert client.closed is True
    # second close must not raise
    adapter.close()


# ---------------------------------------------------------------------------
# Dispatch wiring: network mode (Phase 3) and advanced mode (Phase 4)
# ---------------------------------------------------------------------------


def _drive_until(
    db_session,
    *,
    warmup_session: WarmupSession,
    adapter: MockWarmupTdlibAdapter,
    predicate,
    max_ticks: int = 40,
    when: datetime = datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
) -> None:
    """Гонит несколько dispatch-тиков до выполнения предиката.

    `_select_actions_for_window` дропает 15% действий джиттером — поэтому
    контрактные тесты не должны зависеть от одного успешного тика.
    """
    rng = random.Random(0)
    for tick in range(max_ticks):
        process_due_warmup_dispatches(
            db_session,
            worker_id="w1",
            now=when,
            rng=rng,
            passive_adapter=adapter,
        )
        db_session.refresh(warmup_session)
        if predicate():
            return
        # bring the session back to "due now" so the next tick picks it up
        warmup_session.next_micro_session_at = when
        db_session.commit()
    raise AssertionError(
        f"predicate not satisfied within {max_ticks} ticks; "
        f"adapter.calls={len(adapter.calls)} status={warmup_session.status}"
    )


def test_network_dispatch_calls_join_chat_with_target_from_strategy(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.NETWORK.value,
        target_channels=[{"username": "cool_news"}, {"username": "memes_daily"}],
        daily_action_limits={
            "1": {"feed_read": 0, "join_chat": 1, "p2p_send": 0},
        },
    )
    warmup_session = seed_warmup_session(
        db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    adapter = MockWarmupTdlibAdapter(rng_seed=10)

    _drive_until(
        db_session,
        warmup_session=warmup_session,
        adapter=adapter,
        predicate=lambda: any(c["action_type"] == "join_chat" for c in adapter.calls),
    )

    join_calls = [c for c in adapter.calls if c["action_type"] == "join_chat"]
    assert join_calls, "join_chat must have been invoked"
    assert join_calls[0]["context"]["chat_target"] in {"cool_news", "memes_daily"}
    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters.get("join_chat", 0) == 1
    event_types = [e.event_type for e in warmup_session.events]
    assert "session_action_executed" in event_types


def test_network_dispatch_skips_join_chat_when_strategy_has_no_channels(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.NETWORK.value,
        target_channels=[],
        daily_action_limits={"1": {"join_chat": 1}},
    )
    warmup_session = seed_warmup_session(
        db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    adapter = MockWarmupTdlibAdapter()

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    join_calls = [c for c in adapter.calls if c["action_type"] == "join_chat"]
    assert join_calls == []
    skip_events = [
        e
        for e in warmup_session.events
        if e.event_type == "task_skipped"
        and e.payload_json.get("reason") == "no_target_channels_configured"
    ]
    assert skip_events, "expected no_target_channels_configured skip"
    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters.get("join_chat", 0) == 0


def test_advanced_dispatch_p2p_send_uses_eligible_peer_and_records_contact(
    db_session,
) -> None:
    sender_strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.ADVANCED.value,
        target_channels=[{"username": "cool_news"}],
        daily_action_limits={"1": {"p2p_send": 1}},
    )
    warmup_session = seed_warmup_session(
        db_session, strategy=sender_strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    # seed eligible peer in the same workspace, with telegram_user_id
    peer_account = seed_warmup_account(db_session, telegram_user_id="555")
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=peer_account.id,
            eligible_from=datetime(2026, 7, 1, 0, 0, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    adapter = MockWarmupTdlibAdapter(rng_seed=21)
    _drive_until(
        db_session,
        warmup_session=warmup_session,
        adapter=adapter,
        predicate=lambda: any(c["action_type"] == "p2p_send" for c in adapter.calls),
    )

    db_session.refresh(peer_account)

    p2p_calls = [c for c in adapter.calls if c["action_type"] == "p2p_send"]
    assert len(p2p_calls) >= 1
    ctx = p2p_calls[0]["context"]
    assert ctx["peer_account_id"] == peer_account.id
    assert ctx["peer_telegram_user_id"] == "555"
    assert ctx["text"]
    assert ctx["text_seed"]

    # peer's current_contacts must have been incremented
    peer_row = (
        db_session.query(WarmupTrustedPeer)
        .filter(WarmupTrustedPeer.account_id == peer_account.id)
        .one()
    )
    assert peer_row.current_contacts >= 1

    counters = warmup_session.daily_counters_json.get("0", {})
    assert counters.get("p2p_send", 0) >= 1

    event_types = [e.event_type for e in warmup_session.events]
    assert "p2p_contact_recorded" in event_types
    assert "session_action_executed" in event_types


def test_advanced_dispatch_skips_when_no_eligible_peer(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.ADVANCED.value,
        target_channels=[{"username": "cool_news"}],
        daily_action_limits={"1": {"p2p_send": 1}},
    )
    warmup_session = seed_warmup_session(
        db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    adapter = MockWarmupTdlibAdapter()

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    p2p_calls = [c for c in adapter.calls if c["action_type"] == "p2p_send"]
    assert p2p_calls == []
    skip_events = [
        e
        for e in warmup_session.events
        if e.event_type == "task_skipped" and e.payload_json.get("reason") == "no_friends_available"
    ]
    assert skip_events


def test_dispatch_closes_adapter_after_tick(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.NETWORK.value,
        target_channels=[{"username": "cool"}],
        daily_action_limits={"1": {"join_chat": 1}},
    )
    seed_warmup_session(db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC))

    closed_calls: list[str] = []

    class _CloseTrackingAdapter(MockWarmupTdlibAdapter):
        def close(self) -> None:
            closed_calls.append("closed")

    adapter = _CloseTrackingAdapter(rng_seed=0)
    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        rng=random.Random(0),
        passive_adapter=adapter,
    )
    assert closed_calls == ["closed"]


def test_write_action_blocked_when_adapter_lacks_capability(db_session) -> None:
    """Если стратегия требует p2p_send, но adapter работает в passive-only,
    dispatch пишет write_action_not_enabled и не вызывает adapter."""
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.ADVANCED.value,
        target_channels=[{"username": "cool"}],
        daily_action_limits={"1": {"p2p_send": 1}},
    )
    warmup_session = seed_warmup_session(
        db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    peer_account = seed_warmup_account(db_session, telegram_user_id="777")
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=peer_account.id,
            eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    adapter = MockWarmupTdlibAdapter(supported_modes=("passive",))
    _drive_until(
        db_session,
        warmup_session=warmup_session,
        adapter=adapter,
        predicate=lambda: any(
            e.event_type == "task_skipped"
            and e.payload_json.get("reason") == "write_action_not_enabled"
            for e in warmup_session.events
        ),
    )

    p2p_calls = [c for c in adapter.calls if c["action_type"] == "p2p_send"]
    assert p2p_calls == [], "adapter without p2p capability must not be invoked"
    skip_events = [
        e
        for e in warmup_session.events
        if e.event_type == "task_skipped"
        and e.payload_json.get("reason") == "write_action_not_enabled"
    ]
    assert skip_events


# ---------------------------------------------------------------------------
# warmup_p2p service unit tests
# ---------------------------------------------------------------------------


def test_select_eligible_peer_excludes_sender_and_revoked(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    other = seed_warmup_account(db_session, telegram_user_id="200")
    revoked = seed_warmup_account(db_session, telegram_user_id="300")
    cap_full = seed_warmup_account(db_session, telegram_user_id="400")
    db_session.add_all(
        [
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=sender.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=3,
                current_contacts=0,
            ),
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=other.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=3,
                current_contacts=0,
            ),
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=revoked.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=3,
                current_contacts=0,
                revoked_at=datetime(2026, 7, 15, tzinfo=UTC),
                revoked_reason="manual",
            ),
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=cap_full.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=2,
                current_contacts=2,
            ),
        ]
    )
    db_session.commit()

    pick = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert pick is not None
    assert pick.account_id == other.id
    assert pick.telegram_user_id == "200"


def test_select_eligible_peer_skips_when_eligible_from_in_future(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    future = seed_warmup_account(db_session, telegram_user_id="200")
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=future.id,
            eligible_from=datetime(2027, 1, 1, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    pick = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert pick is None


def test_record_p2p_contact_increments_receiver_and_sender_when_in_pool(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    receiver = seed_warmup_account(db_session, telegram_user_id="200")
    db_session.add_all(
        [
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=sender.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=5,
                current_contacts=1,
            ),
            WarmupTrustedPeer(
                id=new_id(),
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=receiver.id,
                eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
                max_active_contacts=5,
                current_contacts=2,
            ),
        ]
    )
    db_session.commit()

    summary = record_p2p_contact(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        receiver_account_id=receiver.id,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    db_session.commit()

    assert summary == {"receiver_contacts": 3, "sender_contacts": 2}


def test_record_p2p_contact_raises_if_receiver_not_in_pool(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    foreign = seed_warmup_account(db_session, telegram_user_id="200")
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=sender.id,
            eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    try:
        record_p2p_contact(
            db_session,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            sender_account_id=sender.id,
            receiver_account_id=foreign.id,
        )
    except ValueError as exc:
        assert "receiver is not in trusted-peer pool" in str(exc)
    else:
        raise AssertionError("expected ValueError when receiver missing from pool")


def test_text_seed_is_deterministic_across_ticks(db_session) -> None:
    """Один и тот же session+day+action ⇒ один и тот же seed (требование Phase 0a)."""
    from app.services.warmup_dispatch import _derive_text_seed

    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.ADVANCED.value,
        target_channels=[{"username": "cool"}],
        daily_action_limits={"1": {"p2p_send": 1}},
    )
    session_obj = seed_warmup_session(
        db_session, strategy=strategy, now=datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    )
    db_session.refresh(session_obj)

    seed_1 = _derive_text_seed(session_obj, "p2p_send")
    seed_2 = _derive_text_seed(session_obj, "p2p_send")
    seed_other = _derive_text_seed(session_obj, "join_chat")
    assert seed_1 == seed_2
    assert seed_1 != seed_other
    assert len(seed_1) == 32


def test_p2p_select_workspace_isolation(db_session) -> None:
    """Peer'ы из другого workspace'а не должны выбираться.

    SQLite-тесты не enforce'ят FK между workspace и peer/account, поэтому
    тест использует произвольный UUID-string как сторонний workspace_id —
    запрос-фильтр в `select_eligible_peer` обязан строго ограничивать
    выборку рабочей областью вызывающего.
    """
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    foreign_workspace_id = new_id()
    foreign_account = seed_warmup_account(db_session, telegram_user_id="999")
    # переписываем workspace_id для имитации чужой области
    foreign_account.workspace_id = foreign_workspace_id
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=foreign_workspace_id,
            account_id=foreign_account.id,
            eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    pick = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert pick is None, "must not cross workspace boundary"


def test_p2p_select_rejects_peer_row_pointing_to_foreign_account(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    foreign_workspace_id = new_id()
    foreign_account = seed_warmup_account(db_session, telegram_user_id="999")
    foreign_account.workspace_id = foreign_workspace_id
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=foreign_account.id,
            eligible_from=datetime(2026, 7, 1, tzinfo=UTC),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()

    pick = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert pick is None
