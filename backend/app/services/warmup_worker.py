"""Compatibility wrapper.

Canonical owner: app.modules.warmup.worker
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.warmup import worker as _worker
from app.modules.warmup.worker import (
    DRY_RUN_TASK_TYPE,
    claim_account_runtime_lock,
    handle_warmup_step_failure,
    process_due_warmup_sessions,
    release_account_runtime_lock,
)

_complete_session = getattr(_worker, "_complete_session")
_process_one_due_session = getattr(_worker, "_process_one_due_session")
_process_one_locked_session = getattr(_worker, "_process_one_locked_session")

__all__ = [
    "DRY_RUN_TASK_TYPE",
    "_complete_session",
    "_process_one_due_session",
    "_process_one_locked_session",
    "claim_account_runtime_lock",
    "handle_warmup_step_failure",
    "process_due_warmup_sessions",
    "release_account_runtime_lock",
]
