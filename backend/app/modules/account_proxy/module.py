from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_proxy",
    workflows=(),
    router_path="app.modules.account_proxy.router:router",
)

__all__ = ["module"]
