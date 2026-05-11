from __future__ import annotations

import shutil
from typing import Any

from app.config import Settings, settings
from app.services.accounts import get_account
from sqlalchemy.orm import Session


def build_story_capabilities(
    session: Session,
    account_id: str,
    *,
    workspace_id: str | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")

    ffprobe_available = _binary_available(config.ffprobe_path, "ffprobe")
    ffmpeg_available = _binary_available(config.ffmpeg_path, "ffmpeg")
    tdlib_execution_enabled = config.profile_execution_adapter == "tdlib"
    live_enabled = (
        config.stories_enabled and tdlib_execution_enabled and config.stories_tdlib_live_enabled
    )
    return {
        "account_id": account_id,
        "stories_enabled": config.stories_enabled,
        "tdlib_live_publishing_enabled": live_enabled,
        "can_prepare_image": True,
        "can_prepare_video": ffprobe_available and ffmpeg_available,
        "allowed_active_period_seconds": [86400],
        "allowed_privacy_presets": ["contacts", "close_friends", "public"],
        "max_caption_length": 1024,
        "ffprobe_available": ffprobe_available,
        "ffmpeg_available": ffmpeg_available,
        "warnings": _warnings(config, ffprobe_available, ffmpeg_available),
    }


def _binary_available(configured_path: str | None, fallback_name: str) -> bool:
    if configured_path:
        return shutil.which(configured_path) is not None
    return shutil.which(fallback_name) is not None


def _warnings(config: Settings, ffprobe_available: bool, ffmpeg_available: bool) -> list[str]:
    warnings: list[str] = []
    if not config.stories_enabled:
        warnings.append("stories are disabled")
    elif config.profile_execution_adapter != "tdlib":
        warnings.append("stories live TDLib publishing requires TDLib profile execution")
    elif not config.stories_tdlib_live_enabled:
        warnings.append("stories live TDLib publishing is disabled")
    if not ffprobe_available or not ffmpeg_available:
        warnings.append("story video preparation is limited until ffprobe and ffmpeg are available")
    return warnings
