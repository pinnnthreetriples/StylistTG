"""Compatibility wrapper.

Canonical owner: app.modules.account_editing.executor
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.account_editing.executor import (
    execute_account_update_job,
    rematerialize_account_update_job,
    run_account_update_job,
)

__all__ = [
    "execute_account_update_job",
    "rematerialize_account_update_job",
    "run_account_update_job",
]
