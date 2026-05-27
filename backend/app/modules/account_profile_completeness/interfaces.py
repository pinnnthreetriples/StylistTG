"""Narrow public profile-completeness interface for other feature modules."""

from __future__ import annotations

from app.modules.account_profile_completeness.service import evaluate

_PUBLIC_SYMBOL_RATIONALE = {
    "evaluate": "Feature modules can evaluate profile completeness without importing internals.",
}

__all__ = ["evaluate"]
