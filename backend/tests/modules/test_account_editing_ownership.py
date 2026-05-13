from __future__ import annotations

from app.job_queue.workflows import resolve_handler
from app.modules.account_editing import service
from app.modules.registry import get_workflow_spec, iter_workflows


def test_account_editing_service_exports_use_case_facade() -> None:
    assert callable(service.build_preview)
    assert callable(service.create_job)
    assert callable(service.enqueue_job)
    assert callable(service.execute_inline_fallback)


def test_account_editing_planner_exports_legacy_planner_symbols() -> None:
    from app.modules.account_editing import planner

    expected_symbols = {
        "PROFILE_STEP_TYPES",
        "WORKFLOW_TYPE",
        "WORKFLOW_VERSION",
        "JOB_PAYLOAD_VERSION",
        "profile_payload_to_account_update_desired_state",
        "normalize_account_update_desired_state",
        "account_update_profile_payload",
        "canonical_account_update_desired_state",
        "compute_account_update_intent_hash",
        "build_account_update_plan",
        "default_capability_snapshot",
    }

    for symbol in expected_symbols:
        assert hasattr(planner, symbol)


def test_legacy_planner_path_reexports_module_planner_symbols() -> None:
    from app.modules.account_editing import planner
    from app.services import account_update_plan

    assert account_update_plan.build_account_update_plan is planner.build_account_update_plan
    assert (
        account_update_plan.compute_account_update_intent_hash
        is planner.compute_account_update_intent_hash
    )
    assert account_update_plan.WORKFLOW_TYPE == "account_update"


def test_legacy_service_path_delegates_to_module_service(monkeypatch) -> None:
    from app.services import account_update_jobs

    preview_calls: list[dict[str, object]] = []
    create_calls: list[dict[str, object]] = []

    def fake_preview(session: object, **kwargs: object) -> dict[str, object]:
        preview_calls.append({"session": session, **kwargs})
        return {"ok": True}

    def fake_create(session: object, **kwargs: object) -> object:
        create_calls.append({"session": session, **kwargs})
        return object()

    monkeypatch.setattr(
        account_update_jobs.account_editing_service,
        "build_account_update_preview",
        fake_preview,
    )
    monkeypatch.setattr(
        account_update_jobs.account_editing_service,
        "create_account_update_job",
        fake_create,
    )

    session = object()
    assert account_update_jobs.build_account_update_preview(
        session,
        account_id="account-1",
        desired_state={},
        workspace_id="workspace-1",
    ) == {"ok": True}
    created = account_update_jobs.create_account_update_job(
        session,
        account_id="account-1",
        desired_state={},
        workspace_id="workspace-1",
    )

    assert created is create_calls[0]["session"] or created is not None
    assert preview_calls[0]["account_id"] == "account-1"
    assert create_calls[0]["account_id"] == "account-1"


def test_legacy_worker_path_delegates_to_module_executor() -> None:
    from app.modules.account_editing import executor
    from app.workers import account_update_jobs

    assert account_update_jobs.execute_account_update_job is executor.execute_account_update_job
    assert account_update_jobs.run_account_update_job is executor.run_account_update_job
    assert (
        account_update_jobs.rematerialize_account_update_job
        is executor.rematerialize_account_update_job
    )


def test_workflow_handler_still_resolves_to_module_job_entrypoint() -> None:
    from app.modules.account_editing.jobs import run_account_update_job

    workflow = get_workflow_spec("account_update")

    assert workflow.handler_path == "app.modules.account_editing.jobs:run_account_update_job"
    assert resolve_handler(workflow.handler_path) is run_account_update_job


def test_no_account_editing_workflow_type_exists() -> None:
    workflow_types = {workflow.workflow_type for workflow in iter_workflows()}

    assert "account_editing" not in workflow_types
