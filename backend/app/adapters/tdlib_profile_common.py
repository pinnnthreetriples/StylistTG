from __future__ import annotations

from typing import Any, cast

from app.adapters.tdlib_auth import TdlibClient, map_tdlib_error


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


class TdlibProfileQueryError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _checked_send_query(
    client: TdlibClient, query: dict[str, Any], timeout_seconds: float
) -> dict[str, Any]:
    response = client.send_query(query, timeout_seconds)
    if response.get("@type") != "error":
        return response
    mapped = map_tdlib_error(response)
    error_code = _profile_tdlib_error_code(response, mapped.recovery_marker)
    raise TdlibProfileQueryError(mapped.error or "TDLib query failed", error_code=error_code)


def _profile_tdlib_error_code(response: dict[str, Any], recovery_marker: str | None) -> str:
    message = str(response.get("message") or "").strip().upper()
    if message.startswith(("USERNAME_", "FLOOD_", "FROZEN_")):
        return message
    return (recovery_marker or "tdlib_profile_step_failed").removeprefix("tdlib_hard_stop:")
