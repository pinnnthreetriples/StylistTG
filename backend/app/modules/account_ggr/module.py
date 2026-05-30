from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_ggr",
    workflows=(),
    router_path="app.modules.account_ggr.router:router",
)

__all__ = ["module"]
