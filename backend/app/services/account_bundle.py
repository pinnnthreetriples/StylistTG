"""Compatibility wrapper.

Canonical owner: app.modules.account_core.bundle
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import bundle as _bundle_module

sys.modules[__name__] = _bundle_module
