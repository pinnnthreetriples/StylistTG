from __future__ import annotations

"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.status_contracts
Do not add new behavior here.
"""

from app.modules.account_safety.status_contracts import (
    AccountStatusAutoAction,
    AccountStatusObservationRead,
)

__all__ = ["AccountStatusAutoAction", "AccountStatusObservationRead"]
