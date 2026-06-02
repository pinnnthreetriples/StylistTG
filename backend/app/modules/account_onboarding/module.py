from __future__ import annotations

from app.contracts.queues import AUTH_QUEUE_NAME, MAINTENANCE_QUEUE_NAME
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec

module = FeatureModule(
    name="account_onboarding",
    workflows=(
        WorkflowSpec("account_onboarding.item.execute", AUTH_QUEUE_NAME, "app.modules.account_onboarding.workers:run_onboarding_item", WorkflowArgsMode.CUSTOM, "Execute account onboarding items."),
        WorkflowSpec("account_onboarding.artifacts.expire", MAINTENANCE_QUEUE_NAME, "app.modules.account_onboarding.workers:expire_onboarding_artifacts", WorkflowArgsMode.CUSTOM, "Expire private onboarding artifacts."),
    ),
    router_path="app.modules.account_onboarding.router:router",
)

__all__ = ["module"]
