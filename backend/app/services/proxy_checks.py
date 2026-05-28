"""Compatibility wrapper.

Canonical owner: app.modules.account_proxy.checks
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_proxy import checks as _checks_module

sys.modules[__name__] = _checks_module
