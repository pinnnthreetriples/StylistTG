from __future__ import annotations

import dataclasses
import inspect

from app.modules import registry
from app.modules.contracts import FeatureModule, WorkflowArgsMode
from app.modules.registry import get_workflow_spec, iter_modules, iter_workflows


def test_feature_module_does_not_expose_router_yet() -> None:
    field_names = {field.name for field in dataclasses.fields(FeatureModule)}

    assert "router" not in field_names
    assert field_names == {"name", "workflows"}


def test_modules_registry_does_not_import_api_or_fastapi_routers() -> None:
    source = inspect.getsource(registry)

    assert "app.api" not in source
    assert "APIRouter" not in source
    assert "include_router" not in source


def test_account_editing_workflow_type_remains_account_update() -> None:
    workflow = get_workflow_spec("account_update")

    assert workflow.workflow_type == "account_update"
    assert workflow.handler_path.startswith("app.modules.account_editing.")


def test_account_update_canonical_module_is_account_editing() -> None:
    workflow = get_workflow_spec("account_update")

    assert workflow.handler_path == "app.modules.account_editing.jobs:run_account_update_job"


def test_no_account_editing_workflow_type_exists() -> None:
    workflow_types = {workflow.workflow_type for workflow in iter_workflows()}

    assert "account_editing" not in workflow_types


def test_warmup_workflows_remain_no_arg_handlers() -> None:
    assert get_workflow_spec("warmup_due_sessions").args_mode == WorkflowArgsMode.NONE
    assert get_workflow_spec("warmup_dispatch_tick").args_mode == WorkflowArgsMode.NONE


def test_workflow_handler_paths_are_lazy_strings() -> None:
    for workflow in iter_workflows():
        assert isinstance(workflow.handler_path, str)
        assert ":" in workflow.handler_path


def test_workflow_types_are_unique() -> None:
    workflow_types = [workflow.workflow_type for workflow in iter_workflows()]

    assert len(workflow_types) == len(set(workflow_types))


def test_module_names_are_unique() -> None:
    module_names = [module.name for module in iter_modules()]

    assert len(module_names) == len(set(module_names))


def test_legacy_account_update_paths_are_compatibility_wrappers() -> None:
    from app.modules.account_editing import executor, planner
    from app.services import account_update_plan
    from app.workers import account_update_jobs

    assert account_update_plan.build_account_update_plan is planner.build_account_update_plan
    assert account_update_jobs.execute_account_update_job is executor.execute_account_update_job
