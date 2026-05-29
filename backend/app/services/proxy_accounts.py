"""Compatibility wrapper.

Canonical owner: app.modules.account_proxy.accounts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_proxy import accounts as _accounts_module
from app.modules.account_proxy.accounts import (
    SUPPORTED_PROXY_TYPES,
    decrypt_proxy_password,
    delete_account_proxy,
    get_account_proxy,
    proxy_summary,
    proxy_to_dict,
    upsert_account_proxy,
)

__all__ = [
    "SUPPORTED_PROXY_TYPES",
    "decrypt_proxy_password",
    "delete_account_proxy",
    "get_account_proxy",
    "proxy_summary",
    "proxy_to_dict",
    "upsert_account_proxy",
]

sys.modules[__name__] = _accounts_module
