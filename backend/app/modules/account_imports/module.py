from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_imports",
    workflows=(),
    router_path="app.modules.account_imports.router:router",
)

__all__ = ["module"]
