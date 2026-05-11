from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import Settings, settings
from app.models import Account


CAPABILITY_KEYS = (
    "profile_text",
    "username",
    "profile_photo",
    "profile_music",
    "story_post",
    "story_delete",
    "sync",
    "auth",
)


def build_account_capabilities(
    account: Account,
    reasons: list[dict[str, Any]],
    *,
    config: Settings = settings,
    checked_at: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    hard_blocked = any(reason["severity"] == "blocked" for reason in reasons)
    base_state = "blocked" if hard_blocked else "available"
    capabilities = {
        key: _capability(base_state, _reason_codes(reasons), checked_at=checked_at)
        for key in CAPABILITY_KEYS
    }

    if account.profile_audio_state is None and not hard_blocked:
        capabilities["profile_music"] = _capability(
            "unknown",
            ["music_capability_not_checked"],
            checked_at=checked_at,
            source="db_snapshot",
        )

    if hard_blocked:
        return capabilities

    story_reasons: list[str] = []
    if not config.stories_enabled:
        story_reasons.append("stories_disabled")
    elif config.profile_execution_adapter == "tdlib" and not config.stories_tdlib_live_enabled:
        story_reasons.append("stories_live_disabled")
    elif config.profile_execution_adapter != "tdlib":
        story_reasons.append("stories_mock_mode")

    if story_reasons:
        capabilities["story_post"] = _capability("blocked", story_reasons, checked_at=checked_at)

    if not account.story_posts:
        capabilities["story_delete"] = _capability(
            "unknown", ["no_known_story_posts"], checked_at=checked_at
        )
    elif not any(post.can_be_deleted for post in account.story_posts):
        capabilities["story_delete"] = _capability(
            "limited", ["story_delete_not_confirmed"], checked_at=checked_at
        )

    if account.profile_state is None:
        capabilities["sync"] = _capability(
            "limited", ["profile_sync_unknown"], checked_at=checked_at
        )

    reason_codes = _reason_codes(reasons)
    if "username_recently_rejected" in reason_codes:
        capabilities["username"] = _capability(
            "limited", ["username_recently_rejected"], checked_at=checked_at
        )
    story_limit_reasons = [
        code
        for code in reason_codes
        if code
        in {
            "story_weekly_limit",
            "story_active_limit",
            "story_premium_required",
            "story_recently_rejected",
        }
    ]
    if story_limit_reasons and capabilities["story_post"]["state"] != "blocked":
        capabilities["story_post"] = _capability(
            "limited", story_limit_reasons, checked_at=checked_at
        )

    return capabilities


def _capability(
    state: str,
    reasons: list[str],
    *,
    checked_at: datetime | None,
    source: str = "db_snapshot",
) -> dict[str, Any]:
    return {
        "state": state,
        "reason_codes": reasons,
        "label": state,
        "last_checked_at": checked_at,
        "source": source,
    }


def _reason_codes(reasons: list[dict[str, Any]]) -> list[str]:
    return [str(reason["code"]) for reason in reasons]
