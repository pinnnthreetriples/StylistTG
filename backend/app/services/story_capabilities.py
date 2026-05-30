"""Compatibility wrapper.

Canonical owner: app.modules.story.capabilities
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.story import capabilities as _module
from app.modules.story.capabilities import build_story_capabilities

__all__ = ["build_story_capabilities"]

sys.modules[__name__] = _module
