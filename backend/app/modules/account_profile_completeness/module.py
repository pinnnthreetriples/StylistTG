from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_profile_completeness",
    workflows=(),
    router_path="app.modules.account_profile_completeness.router:router",
)

__all__ = ["module"]
