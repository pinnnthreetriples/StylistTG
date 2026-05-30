"""Public cross-module facade for account_ggr.

Other canonical modules should import GGR primitives from here, not from
`calculator` / `fraud_score` directly.
"""

from __future__ import annotations

from app.modules.account_ggr.calculator import (
    backfill_ggr_scores,
    calculate_ggr,
    compute_bucket,
    compute_components,
    compute_score,
    get_ggr_score,
    recalculate_due_scores,
)
from app.modules.account_ggr.fraud_score import (
    FraudAssessment,
    FraudScoreProvider,
    MockFraudScoreProvider,
    ProxyAssessmentInput,
    UnavailableFraudScoreProvider,
    build_fraud_score_provider,
)

__all__ = [
    "FraudAssessment",
    "FraudScoreProvider",
    "MockFraudScoreProvider",
    "ProxyAssessmentInput",
    "UnavailableFraudScoreProvider",
    "backfill_ggr_scores",
    "build_fraud_score_provider",
    "calculate_ggr",
    "compute_bucket",
    "compute_components",
    "compute_score",
    "get_ggr_score",
    "recalculate_due_scores",
]
