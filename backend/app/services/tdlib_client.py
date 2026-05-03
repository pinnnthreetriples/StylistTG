from __future__ import annotations

import json
from typing import Any, Protocol


SENSITIVE_TDLIB_KEYS = {"code", "password", "api_hash", "database_directory", "files_directory"}


class TdlibJsonClient(Protocol):
    def send(self, payload: dict[str, Any]) -> None: ...
    def receive(self, timeout_seconds: float) -> dict[str, Any] | None: ...
    def close(self) -> None: ...


class MockTdlibJsonClient:
    def __init__(self, updates: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self._updates = list(updates or [])

    def send(self, payload: dict[str, Any]) -> None:
        self.requests.append(redact_tdlib_payload(payload))

    def receive(self, timeout_seconds: float) -> dict[str, Any] | None:
        _ = timeout_seconds
        if not self._updates:
            return None
        return self._updates.pop(0)

    def close(self) -> None:
        self._updates.clear()


def redact_tdlib_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key in SENSITIVE_TDLIB_KEYS:
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = redact_tdlib_payload(value)
        else:
            redacted[key] = value
    return redacted


def safe_tdlib_error_message(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, default=str)
    for token in ("code", "password", "api_hash", "auth_key"):
        text = text.replace(token, "[redacted]")
    return text[:300]
