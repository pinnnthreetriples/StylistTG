"""Compatibility wrapper.

Canonical owner: app.modules.account_ggr.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_ggr import contracts as _contracts_module
from app.modules.account_ggr.contracts import (
    GgrBreakdownRead,
    GgrBucket,
    GgrScoreRead,
)

__all__ = ["GgrBreakdownRead", "GgrBucket", "GgrScoreRead"]

sys.modules[__name__] = _contracts_module
