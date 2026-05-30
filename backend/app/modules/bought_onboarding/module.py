from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="bought_onboarding",
    workflows=(),
    router_path="app.modules.bought_onboarding.router:router",
)

__all__ = ["module"]
