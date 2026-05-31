from __future__ import annotations

from typing import Any

from app.adapters.tdlib_auth import TdlibClient
from app.adapters.tdlib_profile_common import _checked_send_query
from app.config import Settings


def _execute_set_pinned_channel(
    client: TdlibClient, step: dict[str, Any], config: Settings
) -> dict[str, Any]:
    payload = step["payload"]
    channel_ref = (payload.get("pinned_channel_ref") or "").strip()
    if not channel_ref:
        _checked_send_query(
            client, {"@type": "setPersonalChat", "chat_id": 0}, config.tdlib_auth_timeout_seconds
        )
        return {"ok": True}
    if channel_ref.startswith("@"):
        return _execute_set_pinned_public_channel(client, channel_ref, config)
    if channel_ref.lstrip("-").isdigit():
        _checked_send_query(
            client,
            {"@type": "setPersonalChat", "chat_id": int(channel_ref)},
            config.tdlib_auth_timeout_seconds,
        )
        return {"ok": True}
    return {
        "failed": True,
        "error_code": "invalid_channel_ref",
        "error_message": f"invalid channel reference: {channel_ref}",
    }


def _execute_set_pinned_public_channel(
    client: TdlibClient, channel_ref: str, config: Settings
) -> dict[str, Any]:
    username = channel_ref.lstrip("@")
    if not username:
        return {
            "failed": True,
            "error_code": "invalid_channel_ref",
            "error_message": "empty username after @",
        }
    search_response = client.send_query(
        {"@type": "searchPublicChat", "username": username}, config.tdlib_auth_timeout_seconds
    )
    if search_response.get("@type") == "error" or search_response.get("@type") != "chat":
        return {
            "failed": True,
            "error_code": "pinned_channel_not_found",
            "error_message": f"channel {channel_ref} not found",
        }
    chat_id = search_response.get("id")
    if not chat_id:
        return {
            "failed": True,
            "error_code": "pinned_channel_not_found",
            "error_message": f"channel {channel_ref} not found",
        }
    _checked_send_query(
        client,
        {"@type": "setPersonalChat", "chat_id": int(chat_id)},
        config.tdlib_auth_timeout_seconds,
    )
    return {"ok": True}
