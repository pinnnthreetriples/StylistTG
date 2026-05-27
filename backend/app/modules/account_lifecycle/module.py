from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_lifecycle",
    workflows=(),
    router_path="app.modules.account_lifecycle.router:router",
)

__all__ = ["module"]
