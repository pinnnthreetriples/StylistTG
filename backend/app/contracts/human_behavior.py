"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import contracts as _contracts_module
from app.modules.human_behavior.contracts import BehaviorProfileRead

__all__ = ["BehaviorProfileRead"]

sys.modules[__name__] = _contracts_module
