from __future__ import annotations

import inspect

from app.modules.account_editing import executor, jobs, policies, repository, service


LEGACY_ACCOUNT_UPDATE_IMPORTS = (
    "app.services.account_update_jobs",
    "app.services.account_update_plan",
    "app.workers.account_update_jobs",
)


def test_account_editing_does_not_import_legacy_account_update_implementation() -> None:
    for module in (service, policies, repository, executor, jobs):
        source = inspect.getsource(module)
        for legacy_import in LEGACY_ACCOUNT_UPDATE_IMPORTS:
            assert legacy_import not in source


def test_legacy_account_update_services_depend_on_module_not_reverse() -> None:
    from app.services import account_update_jobs, account_update_plan
    from app.workers import account_update_jobs as worker_account_update_jobs

    assert "app.modules.account_editing" in inspect.getsource(account_update_jobs)
    assert "app.modules.account_editing" in inspect.getsource(account_update_plan)
    assert "app.modules.account_editing" in inspect.getsource(worker_account_update_jobs)


def test_service_remains_use_case_facade() -> None:
    source = inspect.getsource(service)

    assert "def build_preview(" in source
    assert "def create_job(" in source
    assert "def enqueue_job(" in source
    assert "def execute_inline_fallback(" in source
    assert "AccountEditingPolicy" in source
    assert "AccountEditingRepository" in source


def test_repository_does_not_own_business_policy_logic() -> None:
    source = inspect.getsource(repository)

    assert "AccountState" not in source
    assert "is_account_hard_stopped" not in source
    assert "build_account_safety_for_account" not in source
    assert "is_profile_job_cooldown_active" not in source


def test_executor_ownership_remains_inside_account_editing() -> None:
    assert jobs.run_account_update_job.__module__ == "app.modules.account_editing.jobs"
    assert executor.execute_account_update_job.__module__ == "app.modules.account_editing.executor"
