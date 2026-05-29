from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_jobs",
    workflows=(),
    router_path="app.modules.account_jobs.router:router",
)

__all__ = ["module"]
