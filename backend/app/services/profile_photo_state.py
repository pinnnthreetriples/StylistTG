"""Compatibility wrapper.

Canonical owner: app.modules.account_profile_state.photo
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_profile_state import photo as _module
from app.modules.account_profile_state.photo import (
    batch_latest_profile_photo_asset_ids,
    latest_applied_profile_photo_asset_id,
)

__all__ = [
    "batch_latest_profile_photo_asset_ids",
    "latest_applied_profile_photo_asset_id",
]

sys.modules[__name__] = _module
