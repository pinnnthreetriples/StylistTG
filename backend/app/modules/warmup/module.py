from __future__ import annotations

from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec
from app.services.worker_plane import WARMUP_DISPATCH_QUEUE_NAME, WARMUP_QUEUE_NAME


module = FeatureModule(
    name="warmup",
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
    ),
)
