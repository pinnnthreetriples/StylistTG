"""Warmup module public boundary.

Phase 4 keeps warmup as a mixed wrapper-first module. Public consumers should
use explicit submodule imports from this package; deep service implementation
movement is intentionally deferred.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.contracts import FeatureModule
    from app.modules.warmup import contracts as contracts
    from app.modules.warmup import dispatcher as dispatcher
    from app.modules.warmup import errors as errors
    from app.modules.warmup import events as events
    from app.modules.warmup import isolation as isolation
    from app.modules.warmup import jobs as jobs
    from app.modules.warmup import p2p as p2p
    from app.modules.warmup import policies as policies
    from app.modules.warmup import readiness as readiness
    from app.modules.warmup import repository as repository
    from app.modules.warmup import router as router
    from app.modules.warmup import service as service
    from app.modules.warmup import worker as worker

    module: FeatureModule

_LAZY_SUBMODULES = frozenset(
    {
        "contracts",
        "dispatcher",
        "errors",
        "events",
        "isolation",
        "jobs",
        "p2p",
        "policies",
        "readiness",
        "repository",
        "router",
        "service",
        "worker",
    }
)
_LAZY_FEATURE_EXPORTS = frozenset({"module"})

__all__ = [
    "contracts",
    "dispatcher",
    "errors",
    "events",
    "isolation",
    "jobs",
    "module",
    "p2p",
    "policies",
    "readiness",
    "repository",
    "router",
    "service",
    "worker",
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
