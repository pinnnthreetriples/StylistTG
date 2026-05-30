from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="story",
    workflows=(),
    router_path="app.modules.story.router:router",
)

__all__ = ["module"]
