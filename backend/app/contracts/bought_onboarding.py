"""Compatibility wrapper.

Canonical owner: app.modules.bought_onboarding.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.bought_onboarding import contracts as _contracts_module
from app.modules.bought_onboarding.contracts import (
    BoughtOnboardingStatusRead,
    BoughtOnboardingStep,
)

__all__ = ["BoughtOnboardingStatusRead", "BoughtOnboardingStep"]

sys.modules[__name__] = _contracts_module
