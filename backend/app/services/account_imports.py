"""Compatibility wrapper.

Canonical owner: app.modules.account_imports.service
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_imports import service as _service_module
from app.modules.account_imports.service import (
    confirm_import_batch,
    create_import_batch,
    get_import_batch,
    import_batch_to_dict,
    import_item_to_dict,
    list_import_batches,
    metadata_to_bytes,
    validate_batch,
)

__all__ = [
    "confirm_import_batch",
    "create_import_batch",
    "get_import_batch",
    "import_batch_to_dict",
    "import_item_to_dict",
    "list_import_batches",
    "metadata_to_bytes",
    "validate_batch",
]

sys.modules[__name__] = _service_module
