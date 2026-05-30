"""Compatibility wrapper.

Canonical owner: app.modules.story.posts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.story import posts as _module
from app.modules.story.posts import (
    create_story_post_from_result,
    delete_profile_story,
    list_story_posts,
    story_post_payload,
)

__all__ = [
    "create_story_post_from_result",
    "delete_profile_story",
    "list_story_posts",
    "story_post_payload",
]

sys.modules[__name__] = _module
