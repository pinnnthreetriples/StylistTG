from __future__ import annotations

from app.modules.account_editing.module import module as account_editing_module
from app.modules.contracts import FeatureModule, WorkflowSpec
from app.modules.warmup.module import module as warmup_module


MODULES: tuple[FeatureModule, ...] = (
    account_editing_module,
    warmup_module,
)


def iter_modules() -> tuple[FeatureModule, ...]:
    return MODULES


def iter_workflows() -> tuple[WorkflowSpec, ...]:
    workflows: list[WorkflowSpec] = []
    for module in MODULES:
        workflows.extend(module.workflows)
    return tuple(workflows)


def get_workflow_spec(workflow_type: str) -> WorkflowSpec:
    for workflow in iter_workflows():
        if workflow.workflow_type == workflow_type:
            return workflow
    raise ValueError(f"Unknown workflow_type: {workflow_type}")
