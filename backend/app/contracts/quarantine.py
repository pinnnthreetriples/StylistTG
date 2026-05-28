from __future__ import annotations

"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.quarantine_contracts
Do not add new behavior here.
"""

from app.modules.account_safety.quarantine_contracts import (
    AccountQuarantineRead,
    AdminReasonRequest,
    QuarantineReason,
    ReleaseRequest,
    TerminalStatusClearRead,
)

__all__ = [
    "AccountQuarantineRead",
    "AdminReasonRequest",
    "QuarantineReason",
    "ReleaseRequest",
    "TerminalStatusClearRead",
]
