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

_PUBLIC_SYMBOL_RATIONALE = {
    "SafetyGateReservation": "Typed reservation token used by sender flows to release held capacity.",
    "SafetyGateVerdict": "Stable safety gate decision contract consumed by feature modules.",
    "build_account_safety_for_account": "Account-editing preview reads safety summary for one account.",
    "evaluate": "Feature modules evaluate account safety before write-capable work.",
    "release": "Sender flow releases a previously reserved gate slot.",
    "reserve": "Sender flow reserves gate capacity before TDLib send execution.",
    "safety_preview_fields_with_policy": "Account-editing preview renders safety-policy-aware fields.",
    "unique_preserve_order": "Account-editing preview preserves existing ordered blocker display semantics.",
}

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
