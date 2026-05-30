"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.action_sequencer
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import action_sequencer as _module
from app.modules.human_behavior.action_sequencer import shuffle

__all__ = ["shuffle"]

sys.modules[__name__] = _module
