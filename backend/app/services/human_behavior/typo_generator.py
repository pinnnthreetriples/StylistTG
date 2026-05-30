"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.typo_generator
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import typo_generator as _module
from app.modules.human_behavior.typo_generator import TypoResult, maybe_typo

__all__ = ["TypoResult", "maybe_typo"]

sys.modules[__name__] = _module
