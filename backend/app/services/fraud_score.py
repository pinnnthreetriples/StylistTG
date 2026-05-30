"""Compatibility wrapper.

Canonical owner: app.modules.account_ggr.fraud_score
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_ggr import fraud_score as _module
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
    "build_fraud_score_provider",
]

sys.modules[__name__] = _module
