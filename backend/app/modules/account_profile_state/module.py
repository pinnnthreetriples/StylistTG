from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_profile_state",
    workflows=(),
    router_path=None,
)

__all__ = ["module"]
