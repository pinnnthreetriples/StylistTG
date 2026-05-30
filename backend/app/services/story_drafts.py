"""Compatibility wrapper.

Canonical owner: app.modules.story.drafts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.story import drafts as _module
from app.modules.story.drafts import (
    create_story_draft,
    delete_story_draft,
    delete_story_drafts_for_asset,
    list_story_drafts,
    update_story_draft,
)

__all__ = [
    "create_story_draft",
    "delete_story_draft",
    "delete_story_drafts_for_asset",
    "list_story_drafts",
    "update_story_draft",
]

sys.modules[__name__] = _module
