"""Account editing module public boundary.

The package keeps runtime-heavy facades in submodules to avoid import cycles with
the workflow registry. Public consumers should import the package submodules
explicitly instead of reaching into legacy compatibility paths.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from app.modules.account_editing.errors import (
    AccountAssetKindInvalidError,
    AccountAssetNotFoundError,
    AccountAssetNotReadyError,
    AccountEditingError,
    AccountManualInterventionRequiredError,
    AccountNotFoundError,
    AccountRuntimeUnusableError,
    ProfileAudioUnsupportedFormatError,
    ProfileJobCooldownActiveError,
    StoriesDisabledError,
    StoriesTdlibLiveDisabledError,
)
from app.modules.account_editing.module import module

if TYPE_CHECKING:
    from app.modules.account_editing import router as router

_LAZY_SUBMODULES = frozenset({"router"})

__all__ = [
    "AccountAssetKindInvalidError",
    "AccountAssetNotFoundError",
    "AccountAssetNotReadyError",
    "AccountEditingError",
    "AccountManualInterventionRequiredError",
    "AccountNotFoundError",
    "AccountRuntimeUnusableError",
    "ProfileAudioUnsupportedFormatError",
    "ProfileJobCooldownActiveError",
    "StoriesDisabledError",
    "StoriesTdlibLiveDisabledError",
    "module",
    "router",
]


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_SUBMODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    submodule = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = submodule
    return submodule


def __dir__() -> list[str]:
    return sorted([*globals(), *_LAZY_SUBMODULES])
