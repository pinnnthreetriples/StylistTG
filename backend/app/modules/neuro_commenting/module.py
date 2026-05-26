from __future__ import annotations

from app.contracts.queues import NEURO_COMMENT_QUEUE_NAME
from app.modules.contracts import FeatureModule, WorkflowArgsMode, WorkflowSpec


module = FeatureModule(
    name="neuro_commenting",
    router_path="app.modules.neuro_commenting.router:router",
    workflows=(
        WorkflowSpec(
            workflow_type="neuro_observe_campaign",
            queue_name=NEURO_COMMENT_QUEUE_NAME,
            handler_path="app.modules.neuro_commenting.jobs:run_observe_campaign",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Observe campaign targets for neuro-commenting.",
        ),
        WorkflowSpec(
            workflow_type="neuro_observe_target",
            queue_name=NEURO_COMMENT_QUEUE_NAME,
            handler_path="app.modules.neuro_commenting.jobs:run_observe_target",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Observe one target for neuro-commenting.",
        ),
        WorkflowSpec(
            workflow_type="neuro_generate_comment",
            queue_name=NEURO_COMMENT_QUEUE_NAME,
            handler_path="app.modules.neuro_commenting.jobs:run_generate_comment",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Generate a neuro-comment for an observed post.",
        ),
        WorkflowSpec(
            workflow_type="neuro_refresh_target_metadata",
            queue_name=NEURO_COMMENT_QUEUE_NAME,
            handler_path="app.modules.neuro_commenting.jobs:run_refresh_target_metadata",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Refresh neuro-commenting target metadata.",
        ),
        WorkflowSpec(
            workflow_type="neuro_send_attempt",
            queue_name=NEURO_COMMENT_QUEUE_NAME,
            handler_path="app.modules.neuro_commenting.jobs:run_send_attempt",
            args_mode=WorkflowArgsMode.CUSTOM,
            description="Send a prepared neuro-comment attempt.",
        ),
    ),
)

__all__ = ["module"]
