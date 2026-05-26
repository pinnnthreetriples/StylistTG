"""Canonical neuro-commenting error facade."""

from __future__ import annotations

from app.services.neuro_commenting.errors import (
    NeuroCommentingError,
    NeuroConflictError,
    NeuroNotFoundError,
    NeuroRateLimiterNotReadyError,
    NeuroRuntimeDisabledError,
    NeuroRuntimeUnavailableError,
    NeuroValidationError,
    not_found,
)

__all__ = [
    "NeuroCommentingError",
    "NeuroConflictError",
    "NeuroNotFoundError",
    "NeuroRateLimiterNotReadyError",
    "NeuroRuntimeDisabledError",
    "NeuroRuntimeUnavailableError",
    "NeuroValidationError",
    "not_found",
]
