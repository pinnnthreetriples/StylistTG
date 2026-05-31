from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.warmup_tdlib_errors import _AdapterClientError
from app.adapters.warmup_tdlib_real import RealWarmupTdlibAdapter


class _FakeClient:
    def __init__(self, events: list[dict[str, Any] | None]) -> None:
        self._events = list(events)
        self.closed = False

    def receive(self, _timeout: float) -> dict[str, Any] | None:
        return self._events.pop(0) if self._events else None

    def send(self, _query: dict[str, Any]) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _FakeFactory:
    def __init__(self, clients: list[_FakeClient]) -> None:
        self._clients = list(clients)

    def create(self, _account_id: str) -> _FakeClient:
        return self._clients.pop(0)


def _adapter(client: _FakeClient) -> RealWarmupTdlibAdapter:
    config = SimpleNamespace(
        tdlib_api_id="1",
        tdlib_api_hash="hash",
        tdlib_auth_timeout_seconds=1,
        tdlib_receive_timeout_seconds=0,
    )
    return RealWarmupTdlibAdapter(client_factory=_FakeFactory([client]), config=config)  # type: ignore[arg-type]


def test_ensure_ready_client_caches_only_ready_clients() -> None:
    client = _FakeClient([{"@type": "authorizationStateReady"}])
    adapter = _adapter(client)

    assert adapter._ensure_ready_client("account-1") is client
    assert adapter._ensure_ready_client("account-1") is client
    assert adapter._clients == {"account-1": client}
    assert client.closed is False


def test_ensure_ready_client_closes_and_does_not_cache_tdlib_errors() -> None:
    client = _FakeClient([{"@type": "error", "code": 401, "message": "AUTH_KEY_UNREGISTERED"}])
    adapter = _adapter(client)

    with pytest.raises(_AdapterClientError):
        adapter._ensure_ready_client("account-1")

    assert adapter._clients == {}
    assert client.closed is True


def test_ensure_ready_client_closes_and_does_not_cache_timeout() -> None:
    client = _FakeClient([None, None])
    adapter = _adapter(client)

    with pytest.raises(_AdapterClientError, match="tdlib auth state did not converge"):
        adapter._ensure_ready_client("account-1")

    assert adapter._clients == {}
    assert client.closed is True
