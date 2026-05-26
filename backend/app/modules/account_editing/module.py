from __future__ import annotations

from app.contracts.queues import PROFILE_QUEUE_NAME
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec


module = FeatureModule(
    name="account_editing",
    router_path="app.modules.account_editing.router:router",
    workflows=(
        WorkflowSpec(
            workflow_type="account_update",
            queue_name=PROFILE_QUEUE_NAME,
            handler_path="app.modules.account_editing.jobs:run_account_update_job",
            args_mode=WorkflowArgsMode.JOB_ID,
            description="Manual Telegram account update workflow.",
        ),
    ),
)
