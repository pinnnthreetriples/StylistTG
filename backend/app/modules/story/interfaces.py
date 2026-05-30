"""Public cross-module facade for story."""

from __future__ import annotations

from app.modules.story.capabilities import build_story_capabilities
from app.modules.story.contracts import (
    StoryCapabilitiesRead,
    StoryDraftCreate,
    StoryDraftRead,
    StoryDraftUpdate,
)
from app.modules.story.drafts import (
    create_story_draft,
    delete_story_draft,
    delete_story_drafts_for_asset,
    list_story_drafts,
    update_story_draft,
)
from app.modules.story.posts import (
    create_story_post_from_result,
    delete_profile_story,
    list_story_posts,
    story_post_payload,
)

__all__ = [
    "StoryCapabilitiesRead",
    "StoryDraftCreate",
    "StoryDraftRead",
    "StoryDraftUpdate",
    "build_story_capabilities",
    "create_story_draft",
    "create_story_post_from_result",
    "delete_profile_story",
    "delete_story_draft",
    "delete_story_drafts_for_asset",
    "list_story_drafts",
    "list_story_posts",
    "story_post_payload",
    "update_story_draft",
]
