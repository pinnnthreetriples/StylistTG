"""Compatibility wrapper.

Canonical owner: app.modules.bought_onboarding.service
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.bought_onboarding import service as _module
from app.modules.bought_onboarding.service import (
    REST_PERIOD_HOURS,
    WEAK_GGR_EXTENSION_HOURS,
    BoughtOnboardingNotFound,
    enable_two_factor,
    get_onboarding_state,
    process_rest_period_ggr_check,
    run_rest_period_ggr_check,
    run_terminate_other_sessions,
    start_bought_onboarding,
    status_read,
    terminate_other_sessions,
)

__all__ = [
    "BoughtOnboardingNotFound",
    "REST_PERIOD_HOURS",
    "WEAK_GGR_EXTENSION_HOURS",
    "enable_two_factor",
    "get_onboarding_state",
    "process_rest_period_ggr_check",
    "run_rest_period_ggr_check",
    "run_terminate_other_sessions",
    "start_bought_onboarding",
    "status_read",
    "terminate_other_sessions",
]

sys.modules[__name__] = _module
