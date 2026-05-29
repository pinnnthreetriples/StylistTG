"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.status_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import importlib

_module = importlib.import_module("app.modules.account_safety.status_contracts")

AccountStatusAutoAction = _module.AccountStatusAutoAction
AccountStatusObservationRead = _module.AccountStatusObservationRead

__all__ = ["AccountStatusAutoAction", "AccountStatusObservationRead"]
