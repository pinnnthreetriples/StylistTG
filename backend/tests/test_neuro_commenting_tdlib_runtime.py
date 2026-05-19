from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.services.neuro_commenting.tdlib_runtime import NeuroTdlibRuntime


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        tdlib_auth_timeout_seconds=0.1,
        tdlib_receive_timeout_seconds=0.1,
        tdlib_shared_library_path=None,
    )


def test_ready_client_context_closes_client_on_success() -> None:
    client = _RecordingTdlibClient(responses={"getMe": {"@type": "user", "id": 1}})
    runtime = NeuroTdlibRuntime(config=_config(), client_factory=_Factory(client))

    with runtime.ready_client_context("account-1") as ready:
        assert ready is client

    assert client.close_calls == 1


def test_ready_client_context_closes_client_when_ready_check_fails() -> None:
    client = _RecordingTdlibClient(
        responses={"getMe": {"@type": "error", "message": "UNAUTHORIZED"}}
    )
    runtime = NeuroTdlibRuntime(config=_config(), client_factory=_Factory(client))

    with pytest.raises(NeuroRuntimeUnavailableError):
        with runtime.ready_client_context("account-1"):
            raise AssertionError("client should not be yielded")

    assert client.close_calls == 1


class _RecordingTdlibClient:
    def __init__(self, *, responses: dict[str, dict[str, object]]) -> None:
        self._responses = responses
        self.close_calls = 0

    @property
    def client_id(self) -> int:
        return 1

    def send(self, query: dict[str, object]) -> None:
        _ = query

    def receive(self, timeout_seconds: float) -> dict[str, object] | None:
        _ = timeout_seconds
        return None

    def send_query(self, query: dict[str, object], timeout_seconds: float) -> dict[str, object]:
        _ = timeout_seconds
        return self._responses[str(query["@type"])]

    def close(self) -> None:
        self.close_calls += 1


class _Factory:
    def __init__(self, client: _RecordingTdlibClient) -> None:
        self._client = client

    def create(self, account_id: str) -> _RecordingTdlibClient:
        _ = account_id
        return self._client
