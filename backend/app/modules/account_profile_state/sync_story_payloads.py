from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from .sync_payloads import _extract_text
from .sync_types import JsonDict


def _active_story_payload(story: JsonDict, *, story_poster_chat_id: int | None = None) -> JsonDict:
    story_id = story.get("id")
    poster_chat_id = (
        story.get("story_poster_chat_id") or story.get("poster_chat_id") or story_poster_chat_id
    )
    posted_at = _datetime_from_unix(story.get("date"))
    active_period = 86400
    return {
        "story_poster_chat_id": str(poster_chat_id) if poster_chat_id is not None else None,
        "telegram_story_id": str(story_id) if story_id is not None else None,
        "media_kind": _story_media_kind(story),
        "caption": _extract_text(story.get("caption")),
        "privacy_preset": _story_privacy_preset(story.get("privacy_settings")),
        "active_period_seconds": active_period,
        "can_be_deleted": bool(
            story.get("can_be_deleted") or story.get("can_toggle_is_posted_to_chat_page")
        ),
        "posted_at": posted_at,
        "expires_at": posted_at + timedelta(seconds=active_period) if posted_at else None,
        "raw_tdlib_json": story,
    }


def _story_media_kind(story: JsonDict) -> str:
    content_value = story.get("content")
    content = cast(JsonDict, content_value) if isinstance(content_value, dict) else {}
    content_type = content.get("@type")
    return "video" if content_type == "storyContentVideo" else "image"


def _story_privacy_preset(privacy: object) -> str:
    if not isinstance(privacy, dict):
        return "unknown"
    privacy_payload = cast(JsonDict, privacy)
    return {
        "storyPrivacySettingsEveryone": "public",
        "storyPrivacySettingsContacts": "contacts",
        "storyPrivacySettingsCloseFriends": "close_friends",
        "storyPrivacySettingsSelectedUsers": "selected_users",
    }.get(str(privacy_payload.get("@type")), "unknown")


def _datetime_from_unix(value: object) -> datetime | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, UTC)
