"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.ai_provider_openai
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import ai_provider_openai as _canonical_module

sys.modules[__name__] = _canonical_module
