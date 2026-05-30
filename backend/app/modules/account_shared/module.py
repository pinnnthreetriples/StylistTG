from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_shared",
    workflows=(),
    router_path=None,
)

__all__ = ["module"]
