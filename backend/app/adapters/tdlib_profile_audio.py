from __future__ import annotations

import time
from typing import Any

from app.adapters.tdlib_auth import TdlibClient
from app.adapters.tdlib_profile_common import (
    TdlibProfileQueryError,
    _checked_send_query,
    _dict_or_empty,
)
from app.adapters.tdlib_profile_story import _get_saved_messages_chat_id
from app.config import Settings
from app.logging_utils import log_event


def _tdlib_file_upload_completed(response: dict[str, Any]) -> bool:
    remote = _dict_or_empty(response.get("remote"))
    if not remote:
        return False
    return remote.get("is_uploading_completed") is True


def _tdlib_file_upload_ready_for_profile_audio(response: dict[str, Any]) -> bool:
    if _tdlib_file_upload_completed(response):
        return True
    remote = _dict_or_empty(response.get("remote"))
    if not remote or remote.get("is_uploading_active") is not False:
        return False
    uploaded_size = remote.get("uploaded_size")
    expected_size = response.get("expected_size") or response.get("size")
    if not isinstance(uploaded_size, int) or not isinstance(expected_size, int):
        return False
    return expected_size > 0 and uploaded_size >= expected_size


def _tdlib_file_debug_payload(file_obj: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(file_obj, dict):
        return {}
    remote = _dict_or_empty(file_obj.get("remote"))
    local = _dict_or_empty(file_obj.get("local"))
    payload: dict[str, Any] = {
        "id": file_obj.get("id"),
        "size": file_obj.get("size"),
        "expected_size": file_obj.get("expected_size"),
    }
    if remote:
        payload["remote"] = {
            "is_uploading_active": remote.get("is_uploading_active"),
            "is_uploading_completed": remote.get("is_uploading_completed"),
            "uploaded_size": remote.get("uploaded_size"),
            "has_id": bool(remote.get("id")),
            "has_unique_id": bool(remote.get("unique_id")),
        }
    if local:
        payload["local"] = {
            "is_downloading_completed": local.get("is_downloading_completed"),
            "downloaded_prefix_size": local.get("downloaded_prefix_size"),
        }
    return payload


def wait_for_tdlib_file_upload_completed(
    client: TdlibClient,
    file_response: dict[str, Any],
    timeout_seconds: float,
    receive_timeout_seconds: float,
    *,
    account_id: str | None = None,
    step_key: str | None = None,
    audio_asset_id: str | None = None,
) -> dict[str, Any] | None:
    file_id = file_response.get("id")
    if _tdlib_file_upload_ready_for_profile_audio(file_response):
        return file_response
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        event = client.receive(min(receive_timeout_seconds, max(deadline - time.monotonic(), 0.0)))
        if event is None:
            continue
        if event.get("@type") != "updateFile":
            continue
        updated_file = _dict_or_empty(event.get("file"))
        if not updated_file or updated_file.get("id") != file_id:
            continue
        log_event(
            "tdlib_profile_audio_update_file",
            account_id=account_id,
            step_key=step_key,
            audio_asset_id=audio_asset_id,
            file=_tdlib_file_debug_payload(updated_file),
        )
        if _tdlib_file_upload_ready_for_profile_audio(updated_file):
            return updated_file
    return None


def _upload_profile_audio_via_saved_messages(
    client: TdlibClient,
    step: dict[str, Any],
    config: Settings,
    *,
    account_id: str,
) -> dict[str, Any]:
    payload = step["payload"]
    chat_id = _get_saved_messages_chat_id(client, config)
    message = _checked_send_query(
        client,
        {
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": {
                "@type": "inputMessageAudio",
                "audio": {"@type": "inputFileLocal", "path": payload["asset_path"]},
                "album_cover_thumbnail": None,
                "duration": 0,
                "title": payload.get("title") or "",
                "performer": "",
                "caption": {"@type": "formattedText", "text": "", "entities": []},
            },
        },
        config.tdlib_auth_timeout_seconds,
    )
    final_message = _wait_for_audio_message_send_succeeded(
        client,
        chat_id=chat_id,
        old_message_id=int(message.get("id") or 0),
        config=config,
        account_id=account_id,
        step_key=step["step_key"],
        audio_asset_id=payload.get("audio_asset_id"),
    )
    audio_file = _extract_message_audio_file(final_message)
    audio_file_id = audio_file.get("id")
    if audio_file_id is None:
        raise TdlibProfileQueryError(
            "Telegram sent the audio message, but did not return an audio file identifier",
            error_code="PROFILE_AUDIO_FILE_ID_MISSING",
        )
    log_event(
        "tdlib_profile_audio_saved_message_ready",
        account_id=account_id,
        step_key=step["step_key"],
        audio_asset_id=payload.get("audio_asset_id"),
        chat_id=chat_id,
        message_id=final_message.get("id"),
        file=_tdlib_file_debug_payload(audio_file),
    )
    return {
        "audio_file_id": int(audio_file_id),
        "chat_id": chat_id,
        "message_id": final_message.get("id"),
    }


def _wait_for_audio_message_send_succeeded(
    client: TdlibClient,
    *,
    chat_id: int,
    old_message_id: int,
    config: Settings,
    account_id: str,
    step_key: str,
    audio_asset_id: str | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + config.tdlib_auth_timeout_seconds
    while time.monotonic() < deadline:
        event = client.receive(config.tdlib_receive_timeout_seconds)
        if event is None:
            continue
        event_type = event.get("@type")
        if (
            event_type == "updateMessageSendSucceeded"
            and event.get("old_message_id") == old_message_id
        ):
            message = _dict_or_empty(event.get("message"))
            if message:
                return message
        if (
            event_type == "updateMessageSendFailed"
            and event.get("old_message_id") == old_message_id
        ):
            log_event(
                "tdlib_profile_audio_saved_message_failed",
                account_id=account_id,
                step_key=step_key,
                audio_asset_id=audio_asset_id,
                chat_id=chat_id,
                old_message_id=old_message_id,
                error_code=event.get("error_code"),
                error_message=event.get("error_message"),
            )
            raise TdlibProfileQueryError(
                str(event.get("error_message") or "Telegram did not send the audio message"),
                error_code="PROFILE_AUDIO_MESSAGE_SEND_FAILED",
            )
    raise TdlibProfileQueryError(
        "Telegram did not confirm the temporary audio message",
        error_code="PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT",
    )


def _extract_message_audio_file(message: dict[str, Any]) -> dict[str, Any]:
    content = _dict_or_empty(message.get("content"))
    if content.get("@type") != "messageAudio":
        return {}
    audio = _dict_or_empty(content.get("audio"))
    if not audio:
        return {}
    audio_file = _dict_or_empty(audio.get("audio"))
    if not audio_file:
        return {}
    return audio_file


def _cleanup_temporary_profile_audio_message(
    client: TdlibClient,
    temporary_message: dict[str, Any],
    config: Settings,
    *,
    account_id: str,
    step_key: str,
) -> None:
    chat_id = temporary_message.get("chat_id")
    message_id = temporary_message.get("message_id")
    if chat_id is None or message_id is None:
        return
    try:
        _checked_send_query(
            client,
            {
                "@type": "deleteMessages",
                "chat_id": int(chat_id),
                "message_ids": [int(message_id)],
                "revoke": True,
            },
            config.tdlib_receive_timeout_seconds,
        )
    except Exception as exc:
        log_event(
            "tdlib_profile_audio_temp_message_cleanup_failed",
            account_id=account_id,
            step_key=step_key,
            chat_id=chat_id,
            message_id=message_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )
