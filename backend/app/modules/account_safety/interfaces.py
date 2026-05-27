"""Narrow public account-safety interface for other feature modules."""

from __future__ import annotations

from app.modules.account_safety.gate import evaluate
from app.modules.account_safety.gate_contracts import SafetyGateVerdict
from app.modules.account_safety.read_models import (
    build_account_safety_for_account,
    safety_preview_fields_with_policy,
    unique_preserve_order,
)
from app.modules.account_safety.reserve import SafetyGateReservation, release, reserve

__all__ = [
    "SafetyGateReservation",
    "SafetyGateVerdict",
    "build_account_safety_for_account",
    "evaluate",
    "release",
    "reserve",
    "safety_preview_fields_with_policy",
    "unique_preserve_order",
]
