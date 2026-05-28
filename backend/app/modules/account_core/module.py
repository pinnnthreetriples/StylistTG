from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_core",
    workflows=(),
    router_path="app.modules.account_core.router:router",
)

__all__ = ["module"]
