"""Compatibility wrapper.

Canonical owner: app.modules.account_imports.service
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_imports import service as _service_module

sys.modules[__name__] = _service_module
