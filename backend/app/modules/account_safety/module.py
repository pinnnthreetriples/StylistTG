from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_safety",
    workflows=(),
    router_path="app.modules.account_safety.router:router",
)

__all__ = ["module"]
