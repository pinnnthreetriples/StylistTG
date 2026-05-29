"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.quarantine_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import importlib

_module = importlib.import_module("app.modules.account_safety.quarantine_contracts")

AccountQuarantineRead = _module.AccountQuarantineRead
AdminReasonRequest = _module.AdminReasonRequest
QuarantineReason = _module.QuarantineReason
ReleaseRequest = _module.ReleaseRequest
TerminalStatusClearRead = _module.TerminalStatusClearRead

__all__ = [
    "AccountQuarantineRead",
    "AdminReasonRequest",
    "QuarantineReason",
    "ReleaseRequest",
    "TerminalStatusClearRead",
]
