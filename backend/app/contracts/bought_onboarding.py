"""Compatibility wrapper.

Canonical owner: app.modules.bought_onboarding.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys
from importlib import import_module

_contracts_module = import_module("app.modules.bought_onboarding.contracts")

BoughtOnboardingStatusRead = getattr(_contracts_module, "BoughtOnboardingStatusRead")
BoughtOnboardingStep = getattr(_contracts_module, "BoughtOnboardingStep")

__all__ = ["BoughtOnboardingStatusRead", "BoughtOnboardingStep"]

sys.modules[__name__] = _contracts_module
