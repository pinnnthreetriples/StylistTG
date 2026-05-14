from __future__ import annotations

import sys

from app.modules.account_editing import router as _router_module

sys.modules[__name__] = _router_module
