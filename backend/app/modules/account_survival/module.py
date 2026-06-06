from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_survival",
    workflows=(),
    router_path="app.modules.account_survival.router:router",
)

__all__ = ["module"]
