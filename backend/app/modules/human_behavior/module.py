from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="human_behavior",
    workflows=(),
    router_path="app.modules.human_behavior.router:router",
)

__all__ = ["module"]
