from __future__ import annotations

from app.contracts.queues import AUTH_QUEUE_NAME, MAINTENANCE_QUEUE_NAME
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec

module = FeatureModule(
    name="account_onboarding",
    workflows=(
        WorkflowSpec(
            workflow_type="account_onboarding.item.execute",
            queue_name=AUTH_QUEUE_NAME,
            handler_path="app.modules.account_onboarding.jobs:run_onboarding_item",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Execute account onboarding items.",
        ),
        WorkflowSpec(
            workflow_type="account_onboarding.artifacts.expire",
            queue_name=MAINTENANCE_QUEUE_NAME,
            handler_path="app.modules.account_onboarding.jobs:expire_onboarding_artifacts",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Expire private onboarding artifacts.",
        ),
        WorkflowSpec(
            workflow_type="account_onboarding.artifacts.cleanup_files",
            queue_name=MAINTENANCE_QUEUE_NAME,
            handler_path="app.modules.account_onboarding.jobs:cleanup_onboarding_artifact_files",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Delete expired or rejected private onboarding artifact bytes.",
        ),
    ),
    router_path="app.modules.account_onboarding.router:router",
)

__all__ = ["module"]
