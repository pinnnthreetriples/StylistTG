from __future__ import annotations

from app.contracts.queues import WARMUP_DISPATCH_QUEUE_NAME, WARMUP_QUEUE_NAME
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec


module = FeatureModule(
    name="warmup",
    router_path="app.modules.warmup.router:router",
    workflows=(
        WorkflowSpec(
            workflow_type="warmup_due_sessions",
            queue_name=WARMUP_QUEUE_NAME,
            handler_path="app.modules.warmup.jobs:run_warmup_due_sessions",
            args_mode=WorkflowArgsMode.NONE,
            description="Scan due warmup sessions.",
        ),
        WorkflowSpec(
            workflow_type="warmup_dispatch_tick",
            queue_name=WARMUP_DISPATCH_QUEUE_NAME,
            handler_path="app.modules.warmup.jobs:run_warmup_dispatch_tick",
            args_mode=WorkflowArgsMode.NONE,
            description="Dispatch due warmup micro-sessions.",
        ),
        WorkflowSpec(
            workflow_type="warmup_idle_sweep",
            queue_name=WARMUP_QUEUE_NAME,
            handler_path="app.modules.warmup.jobs:run_warmup_idle_sweep",
            args_mode=WorkflowArgsMode.NONE,
            description="Move idle active accounts into read-only keepalive warmup.",
        ),
        WorkflowSpec(
            workflow_type="warmup_pre_production_sweep",
            queue_name=WARMUP_QUEUE_NAME,
            handler_path="app.modules.warmup.jobs:run_warmup_pre_production_sweep",
            args_mode=WorkflowArgsMode.NONE,
            description="Complete expired empty-profile pre-production sessions.",
        ),
    ),
)
