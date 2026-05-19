from __future__ import annotations

from typing import Any, cast

from app.services.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.services.tdlib_client import safe_tdlib_error_message


def dict_or_empty(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, Any], value)


def checked_tdlib_query(
    client: Any,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        response = client.send_query(payload, timeout_seconds)
    except Exception as exc:
        raise NeuroRuntimeUnavailableError(
            safe_tdlib_error_message(exc), error_code="TDLIB_RUNTIME_UNAVAILABLE"
        ) from exc
    if response.get("@type") == "error":
        raise NeuroRuntimeUnavailableError(
            safe_tdlib_error_message(response), error_code="TDLIB_RUNTIME_UNAVAILABLE"
        )
    return cast(dict[str, Any], response)
