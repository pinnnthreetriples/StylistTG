"""Auth module public boundary."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

from app.modules.auth.context import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_ORDER,
    ROLE_OWNER,
    ROLE_VIEWER,
    AuthContext,
)

if TYPE_CHECKING:
    from app.modules.contracts import FeatureModule
    from app.modules.auth import contracts as contracts
    from app.modules.auth import dependencies as dependencies
    from app.modules.auth import errors as errors
    from app.modules.auth import policies as policies
    from app.modules.auth import repository as repository
    from app.modules.auth import service as service

    module: FeatureModule

_LAZY_SUBMODULES = frozenset(
    {"contracts", "dependencies", "errors", "policies", "repository", "service"}
)
_LAZY_FEATURE_EXPORTS = frozenset({"module"})

__all__ = [
    "AuthContext",
    "ROLE_ADMIN",
    "ROLE_OPERATOR",
    "ROLE_ORDER",
    "ROLE_OWNER",
    "ROLE_VIEWER",
    "contracts",
    "dependencies",
    "errors",
    "module",
    "policies",
    "repository",
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
