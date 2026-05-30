"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.decoy_actions
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import decoy_actions as _module
from app.modules.human_behavior.decoy_actions import DecoyAction, run_before_send

__all__ = ["DecoyAction", "run_before_send"]

sys.modules[__name__] = _module
