from __future__ import annotations

import ctypes
import json
import time
import uuid
from pathlib import Path
from typing import Protocol, cast

from app.adapters.tdlib_auth_states import JsonDict


class TdlibClient(Protocol):
    @property
    def client_id(self) -> int: ...

    def send(self, query: JsonDict) -> None: ...

    def receive(self, timeout_seconds: float) -> JsonDict | None: ...

    def send_query(self, query: JsonDict, timeout_seconds: float) -> JsonDict: ...

    def close(self) -> None: ...


class TdlibClientFactory(Protocol):
    def create(self, account_id: str) -> TdlibClient: ...


class RealTdJsonClient:
    def __init__(self, library: ctypes.CDLL) -> None:
        self._library = library
        self._client = library.td_json_client_create()
        self._closed = False
        self._pending_events: list[JsonDict] = []

    @property
    def client_id(self) -> int:
        return 0

    def send(self, query: JsonDict) -> None:
        self._library.td_json_client_send(self._client, json.dumps(query).encode("utf-8"))

    def receive(self, timeout_seconds: float) -> JsonDict | None:
        if self._pending_events:
            return self._pending_events.pop(0)
        return self._receive_raw(timeout_seconds)

    def _receive_raw(self, timeout_seconds: float) -> JsonDict | None:
        raw = self._library.td_json_client_receive(self._client, timeout_seconds)
        if not raw:
            return None
        raw_value = ctypes.cast(raw, ctypes.c_char_p).value
        if raw_value is None:
            return None
        return cast(JsonDict, json.loads(raw_value.decode("utf-8")))

    def send_query(self, query: JsonDict, timeout_seconds: float) -> JsonDict:
        extra = str(uuid.uuid4())
        self.send({**query, "@extra": extra})
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = self._receive_raw(1.0)
            if not response:
                continue
            if response.get("@extra") == extra:
                return response
            self._pending_events.append(response)
        raise TimeoutError(f"TDLib query timed out: {query.get('@type')}")

    def close(self) -> None:
        if not self._closed:
            self._library.td_json_client_destroy(self._client)
            self._closed = True


class RealTdJsonClientFactory:
    def __init__(self, shared_library_path: Path | None = None) -> None:
        path = str(shared_library_path) if shared_library_path else _default_tdjson_library_name()
        self._library = ctypes.CDLL(path)
        self._library.td_json_client_create.restype = ctypes.c_void_p
        self._library.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._library.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self._library.td_json_client_receive.restype = ctypes.c_char_p
        self._library.td_json_client_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._library.td_json_client_execute.restype = ctypes.c_char_p
        self._library.td_json_client_destroy.argtypes = [ctypes.c_void_p]

    def create(self, account_id: str) -> RealTdJsonClient:
        return RealTdJsonClient(self._library)


class UnavailableTdlibClientFactory:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def create(self, account_id: str) -> TdlibClient:
        raise RuntimeError(self._reason)


def _default_tdjson_library_name() -> str:
    return "tdjson.dll"
