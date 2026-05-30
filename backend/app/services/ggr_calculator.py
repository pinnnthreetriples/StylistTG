"""Compatibility wrapper.

Canonical owner: app.modules.account_ggr.calculator
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_ggr import calculator as _module
from app.modules.account_ggr.calculator import (
    MAX_DELTA_PER_CYCLE,
    RECALC_INTERVAL,
    WEIGHTS,
    backfill_ggr_scores,
    calculate_ggr,
    compute_bucket,
    compute_components,
    compute_score,
    get_ggr_score,
    recalculate_due_scores,
)

__all__ = [
    "MAX_DELTA_PER_CYCLE",
    "RECALC_INTERVAL",
    "WEIGHTS",
    "backfill_ggr_scores",
    "calculate_ggr",
    "compute_bucket",
    "compute_components",
    "compute_score",
    "get_ggr_score",
    "recalculate_due_scores",
]

sys.modules[__name__] = _module
