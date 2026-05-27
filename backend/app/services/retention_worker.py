"""Compatibility wrapper.

Canonical owner: app.modules.account_lifecycle.retention
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_lifecycle import retention as _retention_module

sys.modules[__name__] = _retention_module
