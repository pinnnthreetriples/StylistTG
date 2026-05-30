"""Public cross-module facade for account_profile_state.

Other canonical modules should import profile state primitives from here,
not from `audio` / `photo` / `sync` directly.
"""

from __future__ import annotations

from app.modules.account_profile_state.audio import (
    clear_profile_audio_state,
    profile_audio_state_payload,
    upsert_profile_audio_state,
)
from app.modules.account_profile_state.photo import (
    batch_latest_profile_photo_asset_ids,
    latest_applied_profile_photo_asset_id,
)
from app.modules.account_profile_state.sync import (
    ProfileSyncAdapter,
    TdlibProfileSyncAdapter,
    UnavailableProfileSyncAdapter,
    build_profile_sync_adapter,
    sync_account_live_story_posts,
    sync_account_profile_snapshot,
    sync_account_profile_state,
)

__all__ = [
    "ProfileSyncAdapter",
    "TdlibProfileSyncAdapter",
    "UnavailableProfileSyncAdapter",
    "batch_latest_profile_photo_asset_ids",
    "build_profile_sync_adapter",
    "clear_profile_audio_state",
    "latest_applied_profile_photo_asset_id",
    "profile_audio_state_payload",
    "sync_account_live_story_posts",
    "sync_account_profile_snapshot",
    "sync_account_profile_state",
    "upsert_profile_audio_state",
]
