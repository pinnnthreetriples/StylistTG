"""Warmup module public boundary.

Phase 4 keeps warmup as a mixed wrapper-first module. Public consumers should
use explicit submodule imports from this package; deep service implementation
movement is intentionally deferred.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from app.modules.warmup.module import module

if TYPE_CHECKING:
    from app.modules.warmup import dispatcher as dispatcher
    from app.modules.warmup import events as events
    from app.modules.warmup import isolation as isolation
    from app.modules.warmup import jobs as jobs
    from app.modules.warmup import p2p as p2p
    from app.modules.warmup import readiness as readiness
    from app.modules.warmup import router as router
    from app.modules.warmup import service as service
    from app.modules.warmup import worker as worker

_LAZY_SUBMODULES = frozenset(
    {"dispatcher", "events", "isolation", "jobs", "p2p", "readiness", "router", "service", "worker"}
)

__all__ = [
    "dispatcher",
    "events",
    "isolation",
    "jobs",
    "module",
    "p2p",
    "readiness",
    "router",
    "service",
    "worker",
]


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_SUBMODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    submodule = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = submodule
    return submodule


def __dir__() -> list[str]:
    return sorted([*globals(), *_LAZY_SUBMODULES])
