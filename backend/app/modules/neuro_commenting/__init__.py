"""Neuro-commenting module public boundary."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.contracts import FeatureModule
    from app.modules.neuro_commenting import contracts as contracts
    from app.modules.neuro_commenting import enqueue as enqueue
    from app.modules.neuro_commenting import errors as errors
    from app.modules.neuro_commenting import jobs as jobs
    from app.modules.neuro_commenting import policies as policies
    from app.modules.neuro_commenting import repository as repository
    from app.modules.neuro_commenting import router as router
    from app.modules.neuro_commenting import service as service

    module: FeatureModule

_LAZY_SUBMODULES = frozenset(
    {
        "contracts",
        "enqueue",
        "errors",
        "jobs",
        "policies",
        "repository",
        "router",
        "service",
    }
)
_LAZY_FEATURE_EXPORTS = frozenset({"module"})

__all__ = [
    "contracts",
    "enqueue",
    "errors",
    "jobs",
    "module",
    "policies",
    "repository",
    "router",
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
