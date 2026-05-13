from __future__ import annotations

from app.modules.account_editing import executor, planner, service


def test_old_service_import_paths_still_delegate_to_module_service(monkeypatch) -> None:
    from app.services import account_update_jobs

    calls: list[tuple[str, object, dict[str, object]]] = []

    def fake_preview(session: object, **kwargs: object) -> dict[str, object]:
        calls.append(("preview", session, kwargs))
        return {"can_create_job": True}

    def fake_create(session: object, **kwargs: object) -> object:
        calls.append(("create", session, kwargs))
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
    ) == {"can_create_job": True}
    assert account_update_jobs.create_account_update_job(
        session,
        account_id="account-1",
        desired_state={},
    )
    assert [call[0] for call in calls] == ["preview", "create"]


def test_old_planner_import_path_still_reexports_module_planner() -> None:
    from app.services import account_update_plan

    assert account_update_plan.build_account_update_plan is planner.build_account_update_plan
    assert (
        account_update_plan.compute_account_update_intent_hash
        is planner.compute_account_update_intent_hash
    )


def test_old_worker_import_path_still_reexports_module_executor() -> None:
    from app.workers import account_update_jobs

    assert account_update_jobs.execute_account_update_job is executor.execute_account_update_job
    assert account_update_jobs.run_account_update_job is executor.run_account_update_job
    assert (
        account_update_jobs.rematerialize_account_update_job
        is executor.rematerialize_account_update_job
    )


def test_module_service_is_canonical_for_legacy_create_alias() -> None:
    assert service.create_job_legacy is service.create_account_update_job
