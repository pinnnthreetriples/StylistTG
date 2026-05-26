import pytest

from app.contracts.queues import (
    PROFILE_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
)
from app.modules.contracts import WorkflowArgsMode
from app.modules.registry import (
    get_workflow_spec,
    iter_modules,
    iter_router_paths,
    iter_workflows,
    resolve_router,
)


def test_module_names_are_unique_and_expected_modules_exist() -> None:
    modules = iter_modules()
    names = [module.name for module in modules]

    assert len(names) == len(set(names))
    assert "auth" in names
    assert "account_editing" in names
    assert "warmup" in names


def test_workflow_types_are_unique_and_expected_workflows_exist() -> None:
    workflows = iter_workflows()
    workflow_types = [workflow.workflow_type for workflow in workflows]

    assert len(workflow_types) == len(set(workflow_types))
    assert "account_update" in workflow_types
    assert "warmup_due_sessions" in workflow_types
    assert "warmup_dispatch_tick" in workflow_types


def test_account_update_workflow_metadata_preserves_existing_contract() -> None:
    workflow = get_workflow_spec("account_update")

    assert workflow.queue_name == PROFILE_QUEUE_NAME
    assert workflow.args_mode == WorkflowArgsMode.JOB_ID
    assert workflow.handler_path == "app.modules.account_editing.jobs:run_account_update_job"


def test_warmup_workflow_metadata_uses_no_arg_handlers() -> None:
    due_sessions = get_workflow_spec("warmup_due_sessions")
    dispatch_tick = get_workflow_spec("warmup_dispatch_tick")

    assert due_sessions.queue_name == WARMUP_QUEUE_NAME
    assert due_sessions.args_mode == WorkflowArgsMode.NONE
    assert dispatch_tick.queue_name == WARMUP_DISPATCH_QUEUE_NAME
    assert dispatch_tick.args_mode == WorkflowArgsMode.NONE


def test_unknown_workflow_type_raises_controlled_error() -> None:
    with pytest.raises(ValueError, match="Unknown workflow_type: missing"):
        get_workflow_spec("missing")


def test_router_paths_are_lazy_module_routes() -> None:
    assert iter_router_paths() == (
        "app.modules.account_editing.router:router",
        "app.modules.warmup.router:router",
    )


def test_router_paths_resolve_without_api_wrapper_imports() -> None:
    account_router = resolve_router("app.modules.account_editing.router:router")
    warmup_router = resolve_router("app.modules.warmup.router:router")

    assert account_router.prefix == "/api/account-update"
    assert warmup_router.prefix == "/api/warmup"


def test_module_router_registration_does_not_duplicate_routes() -> None:
    from fastapi.routing import APIRoute

    from app.main import app

    seen: set[tuple[str, tuple[str, ...]]] = set()
    duplicates: list[tuple[str, tuple[str, ...]]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        key = (route.path, tuple(sorted(route.methods or ())))
        if key in seen:
            duplicates.append(key)
        seen.add(key)

    assert duplicates == []
