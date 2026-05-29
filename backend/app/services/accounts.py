"""Compatibility wrapper.

Canonical owner: app.modules.account_core.service
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import service as _service_module
from app.modules.account_core.service import (
    create_account,
    delete_account,
    get_account,
    get_account_by_external_ref,
    list_accounts,
)

__all__ = [
    "create_account",
    "delete_account",
    "get_account",
    "get_account_by_external_ref",
    "list_accounts",
]

sys.modules[__name__] = _service_module
