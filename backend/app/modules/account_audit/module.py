from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_audit",
    workflows=(),
    router_path="app.modules.account_audit.router:router",
)

__all__ = ["module"]
