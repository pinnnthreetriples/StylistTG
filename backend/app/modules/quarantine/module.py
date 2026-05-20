from __future__ import annotations

from app.modules.contracts import FeatureModule

module = FeatureModule(
    name="account_quarantine",
    workflows=(),
    router_path="app.api.account_quarantine_routes:router",
)
