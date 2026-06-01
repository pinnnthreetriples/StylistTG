from __future__ import annotations

from typing import cast

from app.adapters.tdlib_auth import TdlibClient

from .sync_types import JsonDict


def _extract_username(me: JsonDict) -> str | None:
    usernames_value = me.get("usernames")
    usernames = cast(JsonDict, usernames_value) if isinstance(usernames_value, dict) else {}
    editable = usernames.get("editable_username")
    if isinstance(editable, str) and editable:
        return editable
    active = usernames.get("active_usernames")
    if isinstance(active, list) and active and isinstance(active[0], str):
        return active[0]
    return None


def _extract_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        payload = cast(JsonDict, value)
        text = payload.get("text")
        return text if isinstance(text, str) else None
    return None


def _send_query_checked(client: TdlibClient, query: JsonDict, timeout_seconds: float) -> JsonDict:
    response = client.send_query(query, timeout_seconds)
    if response.get("@type") == "error":
        message = response.get("message") or "TDLib query failed"
        raise RuntimeError(str(message))
    return response
