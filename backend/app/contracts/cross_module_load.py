"""Compatibility wrapper.

Canonical owner: app.modules.account_core.cross_module_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import cross_module_contracts as _contracts_module

sys.modules[__name__] = _contracts_module
