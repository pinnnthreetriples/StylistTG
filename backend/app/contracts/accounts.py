"""Compatibility wrapper.

Canonical owner: app.modules.account_core.account_contracts
Do not add new behavior here.
"""

from __future__ import annotations

from importlib import import_module
import sys

_contracts_module = import_module("app.modules.account_core.account_contracts")

ProfileAudioAction = getattr(_contracts_module, "ProfileAudioAction")
ProfilePreviewRead = getattr(_contracts_module, "ProfilePreviewRead")
ProfilePreviewStepRead = getattr(_contracts_module, "ProfilePreviewStepRead")

__all__ = ["ProfileAudioAction", "ProfilePreviewRead", "ProfilePreviewStepRead"]

sys.modules[__name__] = _contracts_module
