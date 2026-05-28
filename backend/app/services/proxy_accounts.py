"""Compatibility wrapper.

Canonical owner: app.modules.account_proxy.accounts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_proxy import accounts as _accounts_module

sys.modules[__name__] = _accounts_module
