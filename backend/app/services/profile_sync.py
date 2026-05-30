"""Compatibility wrapper.

Canonical owner: app.modules.account_profile_state.sync
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_profile_state import sync as _module
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
    "build_profile_sync_adapter",
    "sync_account_live_story_posts",
    "sync_account_profile_snapshot",
    "sync_account_profile_state",
]

sys.modules[__name__] = _module
