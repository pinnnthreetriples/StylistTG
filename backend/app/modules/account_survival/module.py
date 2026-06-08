from __future__ import annotations

from app.contracts.queues import MAINTENANCE_QUEUE_NAME
from app.modules.account_survival.metrics_updater import SURVIVAL_METRICS_WORKFLOW_TYPE
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec

module = FeatureModule(
    name="account_survival",
    workflows=(
        WorkflowSpec(
            workflow_type=SURVIVAL_METRICS_WORKFLOW_TYPE,
            queue_name=MAINTENANCE_QUEUE_NAME,
            handler_path="app.modules.account_survival.metrics_updater:update_survival_metrics_workflow",
            args_mode=WorkflowArgsMode.NONE,
            description="Refresh Advanced Warmup survival Prometheus gauges.",
        ),
    ),
    router_path="app.modules.account_survival.router:router",
)

__all__ = ["module"]
