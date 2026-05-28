"""Compatibility wrapper.

Canonical owner: app.modules.account_core.account_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import account_contracts as _contracts_module

sys.modules[__name__] = _contracts_module
