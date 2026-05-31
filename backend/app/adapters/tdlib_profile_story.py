from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

import time
from typing import Any

from app.adapters.tdlib_auth import TdlibClient
from app.adapters.tdlib_profile_common import (
    TdlibProfileQueryError,
    _checked_send_query,
    _dict_or_empty,
)
from app.config import Settings


class TdlibStoryPostUncertain(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        uncertain_reason: str,
        verification_result: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.uncertain_reason = uncertain_reason
        self.verification_result = verification_result
        self.result_payload = result_payload


def _uncertain_story_step_result(exc: TdlibStoryPostUncertain, event: dict[str, Any]):
    from app.adapters.tdlib_profile_steps import _StepExecutionResult

    return _StepExecutionResult(
        events=[
            {
                "event": "step_uncertain",
                **event,
                "verification_attempted": True,
                "verification_result": exc.verification_result,
                "uncertain_reason": exc.uncertain_reason,
                "result_payload": exc.result_payload,
            },
            {"event": "runtime_closed"},
        ],
        stop_runtime=True,
    )


def _post_story(client: TdlibClient, step: dict[str, Any], config: Settings) -> dict[str, Any]:
    payload = step["payload"]
    media_kind = "image" if step["step_type"] == "post_story_image" else "video"
    chat_id = _get_saved_messages_chat_id(client, config)
    _ensure_can_post_story(client, chat_id, config)
    temporary_story = _checked_send_query(
        client,
        {
            "@type": "postStory",
            "chat_id": chat_id,
            "content": _story_content(media_kind, payload["asset_path"]),
            "areas": {"@type": "inputStoryAreas", "areas": []},
            "caption": {
                "@type": "formattedText",
                "text": payload.get("caption") or "",
                "entities": [],
            },
            "privacy_settings": _story_privacy_settings(payload.get("privacy_preset")),
            "album_ids": [],
            "active_period": int(payload.get("active_period_seconds") or 86400),
            "from_story_full_id": None,
            "is_posted_to_chat_page": False,
            "protect_content": bool(payload.get("protect_content")),
        },
        config.tdlib_auth_timeout_seconds,
    )
    temporary_story_id = temporary_story.get("id")
    if temporary_story_id is None:
        raise TdlibProfileQueryError(
            "TDLib postStory did not return temporary story id",
            error_code="STORY_POST_TEMPORARY_ID_MISSING",
        )
    final_story = _wait_for_story_post_confirmation(client, int(temporary_story_id), config)
    story_id = str(final_story.get("id") or "")
    return {
        "asset_id": payload.get("asset_id"),
        "media_kind": media_kind,
        "caption": payload.get("caption") or "",
        "privacy_preset": payload.get("privacy_preset") or "contacts",
        "active_period_seconds": int(payload.get("active_period_seconds") or 86400),
        "protect_content": bool(payload.get("protect_content")),
        "telegram_story_id": story_id,
        "temporary_story_id": str(temporary_story_id or ""),
        "status": "posted",
        "raw_tdlib_json": final_story,
    }


def _story_content(media_kind: str, asset_path: str) -> dict[str, Any]:
    if media_kind == "image":
        return {
            "@type": "inputStoryContentPhoto",
            "photo": {"@type": "inputFileLocal", "path": asset_path},
            "added_sticker_file_ids": [],
        }
    return {
        "@type": "inputStoryContentVideo",
        "video": {"@type": "inputFileLocal", "path": asset_path},
        "added_sticker_file_ids": [],
        "duration": 0,
        "cover_frame_timestamp": 0,
        "is_animation": False,
    }


def _wait_for_story_post_confirmation(
    client: TdlibClient, temporary_story_id: int, config: Settings
) -> dict[str, Any]:
    deadline = time.monotonic() + min(config.tdlib_auth_timeout_seconds, 30.0)
    while time.monotonic() < deadline:
        event = client.receive(config.tdlib_receive_timeout_seconds)
        if event is None:
            continue
        event_type = event.get("@type")
        if (
            event_type == "updateStoryPostSucceeded"
            and event.get("old_story_id") == temporary_story_id
        ):
            story = _dict_or_empty(event.get("story"))
            if story:
                return story
        if event_type == "updateStoryPostFailed":
            story = _dict_or_empty(event.get("story"))
            if story.get("id") == temporary_story_id:
                error = _dict_or_empty(event.get("error"))
                raise TdlibProfileQueryError(
                    str(error.get("message") or "TDLib story post failed"),
                    error_code=str(error.get("message") or "STORY_POST_FAILED"),
                )
    temporary_payload = {
        "story_post": {
            "temporary_story_id": str(temporary_story_id),
            "telegram_story_id": None,
            "status": "posting",
        }
    }
    raise TdlibStoryPostUncertain(
        "Timed out waiting for TDLib story post confirmation",
        uncertain_reason="story_post_confirmation_timeout",
        verification_result={"temporary_story_id": str(temporary_story_id), "status": "posting"},
        result_payload=temporary_payload,
    )


def _get_saved_messages_chat_id(client: TdlibClient, config: Settings) -> int:
    me = _checked_send_query(client, {"@type": "getMe"}, config.tdlib_receive_timeout_seconds)
    user_id = me.get("id")
    if user_id is None:
        raise TdlibProfileQueryError(
            "TDLib getMe did not return user id", error_code="TDLIB_GET_ME_MISSING_ID"
        )
    chat = _checked_send_query(
        client,
        {"@type": "createPrivateChat", "user_id": int(user_id), "force": True},
        config.tdlib_auth_timeout_seconds,
    )
    chat_id = chat.get("id")
    if chat_id is None:
        raise TdlibProfileQueryError(
            "TDLib createPrivateChat did not return chat id",
            error_code="TDLIB_SAVED_MESSAGES_CHAT_MISSING_ID",
        )
    return int(chat_id)


def _ensure_can_post_story(client: TdlibClient, chat_id: int, config: Settings) -> None:
    response = _checked_send_query(
        client,
        {"@type": "canPostStory", "chat_id": chat_id},
        config.tdlib_auth_timeout_seconds,
    )
    response_type = response.get("@type")
    if response_type == "canPostStoryResultOk":
        return
    raise TdlibProfileQueryError(
        f"TDLib rejected story posting: {response_type or 'unknown'}",
        error_code=_can_post_story_error_code(response_type),
    )


def _story_privacy_settings(preset: str | None) -> dict[str, Any]:
    if preset in {None, "", "contacts"}:
        return {"@type": "storyPrivacySettingsContacts", "except_user_ids": []}
    if preset == "public":
        return {"@type": "storyPrivacySettingsEveryone", "except_user_ids": []}
    if preset == "close_friends":
        return {"@type": "storyPrivacySettingsCloseFriends"}
    raise TdlibProfileQueryError(
        f"Unsupported story privacy preset: {preset}",
        error_code="STORY_PRIVACY_PRESET_UNSUPPORTED",
    )


def _can_post_story_error_code(response_type: str | None) -> str:
    if not response_type:
        return "CAN_POST_STORY_UNKNOWN"
    code = response_type.removeprefix("canPostStoryResult")
    normalized = "".join(f"_{char}" if char.isupper() else char for char in code).strip("_").upper()
    return f"CAN_POST_STORY_{normalized or 'UNKNOWN'}"
