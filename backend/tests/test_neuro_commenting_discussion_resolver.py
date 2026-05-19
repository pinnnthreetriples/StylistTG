from __future__ import annotations

from types import SimpleNamespace

from app.services.neuro_commenting.discussion_resolver import (
    FakeDiscussionMessageResolver,
    TdlibDiscussionMessageResolver,
)


def test_fake_discussion_resolver_returns_configured_mapping() -> None:
    resolver = FakeDiscussionMessageResolver(
        discussion_chat_id="456",
        discussion_message_id="789",
    )

    result = resolver.resolve(
        account_id="account-1",
        target=SimpleNamespace(discussion_chat_id="456"),
        source_chat_id="123",
        source_message_id="111",
    )

    assert result.discussion_chat_id == "456"
    assert result.discussion_message_id == "789"
    assert result.error_code is None


def test_tdlib_discussion_resolver_matches_forward_source_message() -> None:
    client = _RecordingTdlibClient(
        responses={
            "getMe": {"@type": "user", "id": 1},
            "getChatHistory": {
                "@type": "messages",
                "messages": [
                    {
                        "@type": "message",
                        "chat_id": 456,
                        "id": 789,
                        "forward_info": {
                            "@type": "messageForwardInfo",
                            "source": {
                                "@type": "forwardSource",
                                "chat_id": 123,
                                "message_id": 111,
                            },
                        },
                    }
                ],
            },
        }
    )
    resolver = TdlibDiscussionMessageResolver(
        config=SimpleNamespace(tdlib_auth_timeout_seconds=0.1, tdlib_receive_timeout_seconds=0.1),
        client_factory=_Factory(client),
    )

    result = resolver.resolve(
        account_id="account-1",
        target=SimpleNamespace(discussion_chat_id="456"),
        source_chat_id="123",
        source_message_id="111",
    )

    assert result.discussion_chat_id == "456"
    assert result.discussion_message_id == "789"
    assert result.error_code is None
    assert client.close_calls == 1


def test_tdlib_discussion_resolver_returns_error_when_not_found() -> None:
    client = _RecordingTdlibClient(
        responses={
            "getMe": {"@type": "user", "id": 1},
            "getChatHistory": {"@type": "messages", "messages": []},
        }
    )
    resolver = TdlibDiscussionMessageResolver(
        config=SimpleNamespace(tdlib_auth_timeout_seconds=0.1, tdlib_receive_timeout_seconds=0.1),
        client_factory=_Factory(client),
    )

    result = resolver.resolve(
        account_id="account-1",
        target=SimpleNamespace(discussion_chat_id="456"),
        source_chat_id="123",
        source_message_id="111",
    )

    assert result.discussion_chat_id == "456"
    assert result.discussion_message_id is None
    assert result.error_code == "DISCUSSION_MESSAGE_NOT_RESOLVED"
    assert client.close_calls == 1


def test_tdlib_discussion_resolver_requires_discussion_chat() -> None:
    resolver = FakeDiscussionMessageResolver(discussion_chat_id=None, discussion_message_id=None)

    result = resolver.resolve(
        account_id="account-1",
        target=SimpleNamespace(discussion_chat_id=None),
        source_chat_id="123",
        source_message_id="111",
    )

    assert result.error_code == "TARGET_NO_DISCUSSION"


class _RecordingTdlibClient:
    def __init__(self, *, responses: dict[str, dict[str, object]]) -> None:
        self._responses = responses
        self.queries: list[dict[str, object]] = []
        self.close_calls = 0

    @property
    def client_id(self) -> int:
        return 1

    def send(self, query: dict[str, object]) -> None:
        self.queries.append(query)

    def receive(self, timeout_seconds: float) -> dict[str, object] | None:
        _ = timeout_seconds
        return None

    def send_query(self, query: dict[str, object], timeout_seconds: float) -> dict[str, object]:
        _ = timeout_seconds
        self.queries.append(query)
        return self._responses[str(query["@type"])]

    def close(self) -> None:
        self.close_calls += 1


class _Factory:
    def __init__(self, client: _RecordingTdlibClient) -> None:
        self._client = client

    def create(self, account_id: str) -> _RecordingTdlibClient:
        _ = account_id
        return self._client
