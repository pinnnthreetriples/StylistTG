"""Account-safety module public boundary."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.account_safety import contracts as contracts
    from app.modules.account_safety import service as service
    from app.modules.contracts import FeatureModule

    module: FeatureModule

_LAZY_SUBMODULES = frozenset({"contracts", "service"})
_LAZY_FEATURE_EXPORTS = frozenset({"module"})

__all__ = [
    "contracts",
    "module",
    "service",
]


def __getattr__(name: str) -> ModuleType | Any:
    if name in _LAZY_FEATURE_EXPORTS:
        value = getattr(importlib.import_module(f"{__name__}.{name}"), name)
        globals()[name] = value
        return value
    if name not in _LAZY_SUBMODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    submodule = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = submodule
    return submodule


def __dir__() -> list[str]:
    return sorted([*globals(), *_LAZY_FEATURE_EXPORTS, *_LAZY_SUBMODULES])
