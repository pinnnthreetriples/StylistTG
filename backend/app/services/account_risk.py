"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.risk
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.account_safety.risk import (
    build_account_readiness_risk,
    build_account_readiness_risk_summary,
    build_risk_by_operation,
    overall_risk_level,
)

__all__ = [
    "build_account_readiness_risk",
    "build_account_readiness_risk_summary",
    "build_risk_by_operation",
    "overall_risk_level",
]
