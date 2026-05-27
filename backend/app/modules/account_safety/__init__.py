"""Account-safety module public boundary."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.account_safety import accounts_router as accounts_router
    from app.modules.account_safety import action_gate as action_gate
    from app.modules.account_safety import batch_preview as batch_preview
    from app.modules.account_safety import cache as cache
    from app.modules.account_safety import contracts as contracts
    from app.modules.account_safety import gate as gate
    from app.modules.account_safety import gate_contracts as gate_contracts
    from app.modules.account_safety import overrides as overrides
    from app.modules.account_safety import policy as policy
    from app.modules.account_safety import policy_router as policy_router
    from app.modules.account_safety import read_contracts as read_contracts
    from app.modules.account_safety import read_models as read_models
    from app.modules.account_safety import reserve as reserve
    from app.modules.account_safety import service as service
    from app.modules.contracts import FeatureModule

    module: FeatureModule

_LAZY_SUBMODULES = frozenset(
    {
        "accounts_router",
        "action_gate",
        "batch_preview",
        "cache",
        "contracts",
        "gate",
        "gate_contracts",
        "overrides",
        "policy",
        "policy_router",
        "read_contracts",
        "read_models",
        "reserve",
        "service",
    }
)
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
