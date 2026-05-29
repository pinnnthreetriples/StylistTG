"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.quarantine
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.account_safety.quarantine import (
    AccountQuarantineService,
    QuarantineNotFound,
    admin_override_release,
    create_quarantine,
    get_active_quarantine,
    get_unreleased_quarantine,
    handle_flood_wait,
    is_account_quarantined,
    release_quarantine,
)

__all__ = [
    "AccountQuarantineService",
    "QuarantineNotFound",
    "admin_override_release",
    "create_quarantine",
    "get_active_quarantine",
    "get_unreleased_quarantine",
    "handle_flood_wait",
    "is_account_quarantined",
    "release_quarantine",
]
