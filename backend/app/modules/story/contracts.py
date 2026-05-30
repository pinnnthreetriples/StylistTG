"""Module-local DTO re-export.

Story DTOs currently live in the platform-wide `app.schemas` aggregate
to keep the OpenAPI surface stable. This module re-exports the
relevant types so callers can depend on `app.modules.story.contracts`
without reaching into the platform DTO bag.
"""

from __future__ import annotations

from app.schemas import (
    StoryCapabilitiesRead,
    StoryDraftCreate,
    StoryDraftRead,
    StoryDraftUpdate,
)

__all__ = [
    "StoryCapabilitiesRead",
    "StoryDraftCreate",
    "StoryDraftRead",
    "StoryDraftUpdate",
]
