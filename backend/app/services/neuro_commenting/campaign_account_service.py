"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.campaign_account_service
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import campaign_account_service as _canonical_module

sys.modules[__name__] = _canonical_module
