from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

from app.modules.account_audit.module import module as account_audit_module
from app.modules.account_core.module import module as account_core_module
from app.modules.account_editing.module import module as account_editing_module
from app.modules.account_imports.module import module as account_imports_module
from app.modules.account_jobs.module import module as account_jobs_module
from app.modules.account_lifecycle.module import module as account_lifecycle_module
from app.modules.account_profile_completeness.module import (
    module as account_profile_completeness_module,
)
from app.modules.account_proxy.module import module as account_proxy_module
from app.modules.account_safety.module import module as account_safety_module
from app.modules.auth.module import module as auth_module
from app.modules.contracts import FeatureModule, WorkflowSpec
from app.modules.neuro_commenting.module import module as neuro_commenting_module
from app.modules.warmup.module import module as warmup_module


MODULES: tuple[FeatureModule, ...] = (
    auth_module,
    account_audit_module,
    account_core_module,
    account_imports_module,
    account_jobs_module,
    account_safety_module,
    account_editing_module,
    account_lifecycle_module,
    account_profile_completeness_module,
    account_proxy_module,
    warmup_module,
    neuro_commenting_module,
)


def iter_modules() -> tuple[FeatureModule, ...]:
    return MODULES


def iter_workflows() -> tuple[WorkflowSpec, ...]:
    workflows: list[WorkflowSpec] = []
    for module in MODULES:
        workflows.extend(module.workflows)
    return tuple(workflows)


def iter_router_paths() -> tuple[str, ...]:
    return tuple(module.router_path for module in MODULES if module.router_path is not None)


def resolve_router(router_path: str) -> Any:
    module_name, router_name = router_path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, router_name)


def iter_routers() -> Iterator[Any]:
    for router_path in iter_router_paths():
        yield resolve_router(router_path)


def get_workflow_spec(workflow_type: str) -> WorkflowSpec:
    for workflow in iter_workflows():
        if workflow.workflow_type == workflow_type:
            return workflow
    raise ValueError(f"Unknown workflow_type: {workflow_type}")
