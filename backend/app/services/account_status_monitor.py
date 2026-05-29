"""Compatibility wrapper.
Canonical owner: app.modules.account_safety.status_monitor
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.modules.account_safety.status_monitor import (
    AccountStatusMonitor,
    AccountStatusProbeResult,
    DatabaseSnapshotStatusProbe,
    STATUS_MONITOR_CHECKPOINT_KEY,
    STATUS_MONITOR_LOCK_KEY,
    StatusMonitorReport,
    is_in_ip_change_cooldown,
    run_account_status_monitor_tick,
)

_module = importlib.import_module("app.modules.account_safety.status_monitor")
_supports_skip_locked: Callable[[Session], bool] = getattr(_module, "_supports_skip_locked")

__all__ = [
    "AccountStatusMonitor",
    "AccountStatusProbeResult",
    "DatabaseSnapshotStatusProbe",
    "STATUS_MONITOR_CHECKPOINT_KEY",
    "STATUS_MONITOR_LOCK_KEY",
    "StatusMonitorReport",
    "_supports_skip_locked",
    "is_in_ip_change_cooldown",
    "run_account_status_monitor_tick",
]
