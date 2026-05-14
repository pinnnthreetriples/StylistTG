from __future__ import annotations

import inspect

from app.job_queue.workflows import resolve_handler
from app.modules.contracts import WorkflowArgsMode
from app.modules.registry import get_workflow_spec, iter_workflows
from app.services.worker_plane import WARMUP_DISPATCH_QUEUE_NAME, WARMUP_QUEUE_NAME


def test_warmup_workflow_contracts_are_no_arg_module_handlers() -> None:
    due = get_workflow_spec("warmup_due_sessions")
    dispatch = get_workflow_spec("warmup_dispatch_tick")

    assert due.queue_name == WARMUP_QUEUE_NAME
    assert due.args_mode == WorkflowArgsMode.NONE
    assert due.handler_path == "app.modules.warmup.jobs:run_warmup_due_sessions"
    assert dispatch.queue_name == WARMUP_DISPATCH_QUEUE_NAME
    assert dispatch.args_mode == WorkflowArgsMode.NONE
    assert dispatch.handler_path == "app.modules.warmup.jobs:run_warmup_dispatch_tick"


def test_warmup_handlers_resolve_lazily_and_are_no_arg_callables() -> None:
    for workflow_type in ("warmup_due_sessions", "warmup_dispatch_tick"):
        handler = resolve_handler(get_workflow_spec(workflow_type).handler_path)

        assert callable(handler)
        assert len(inspect.signature(handler).parameters) == 0


def test_workflow_types_remain_unique_and_do_not_include_account_editing() -> None:
    workflow_types = [workflow.workflow_type for workflow in iter_workflows()]

    assert len(workflow_types) == len(set(workflow_types))
    assert "account_editing" not in workflow_types
