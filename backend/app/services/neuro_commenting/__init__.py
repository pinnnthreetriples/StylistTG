"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.neuro_commenting.account_selector import AccountSelectionResult, AccountSelector
from app.modules.neuro_commenting.ai_comment_generator import (
    AICommentGenerator,
    AICommentProvider,
    FakeAICommentProvider,
    GeneratedCommentText,
)
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.prompt_builder import BASE_PROMPT, BuiltPrompt, PromptBuilder
from app.modules.neuro_commenting.rate_limiter import NeuroCommentRateLimiter, RateLimitReservation
from app.modules.neuro_commenting.safety_policy import SafetyDecision, SafetyPolicy
from app.modules.neuro_commenting.sender_service import PreparedSend, SenderService

__all__ = [
    "AICommentGenerator",
    "AICommentProvider",
    "AccountSelectionResult",
    "AccountSelector",
    "AnalyticsService",
    "BASE_PROMPT",
    "BuiltPrompt",
    "FakeAICommentProvider",
    "GeneratedCommentText",
    "NeuroCommentRateLimiter",
    "PreparedSend",
    "PromptBuilder",
    "RateLimitReservation",
    "SafetyDecision",
    "SafetyPolicy",
    "SenderService",
]
