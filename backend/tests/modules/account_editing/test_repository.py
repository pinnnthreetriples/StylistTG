from __future__ import annotations

from typing import Any

import pytest

from app.models import Job, JobState, utc_now
from app.models import AccountState
from app.modules.account_editing.errors import (
    AccountManualInterventionRequiredError,
    AccountNotFoundError,
    AccountRuntimeUnusableError,
)
from app.modules.account_editing.planner import (
    account_update_profile_payload,
    build_account_update_plan,
    compute_account_update_intent_hash,
    default_capability_snapshot,
    normalize_account_update_desired_state,
)
from app.modules.account_editing.repository import AccountEditingRepository
from tests.helpers.factories import seed_account_with_profile


def _queued_account_update_job(account_id: str, workspace_id: str) -> Job:
    desired_state = normalize_account_update_desired_state({"profile": {"name": "Stylist TG"}})
    return Job(
        workspace_id=workspace_id,
        account_id=account_id,
        job_state=JobState.QUEUED,
        workflow_type="account_update",
        workflow_version=1,
        execution_intent_hash=compute_account_update_intent_hash(account_id, desired_state),
        job_payload_version=2,
        payload_json=account_update_profile_payload(desired_state),
        desired_state_json=desired_state,
        capability_snapshot_json=default_capability_snapshot(),
        plan_json_snapshot=build_account_update_plan(desired_state),
        queued_at=utc_now(),
    )


def test_require_account_raises_exact_missing_account_error(db_session) -> None:
    with pytest.raises(AccountNotFoundError, match="^account not found$"):
        AccountEditingRepository(db_session).require_account(account_id="missing")


def test_validate_account_for_job_raises_typed_manual_intervention_error(db_session) -> None:
    account = seed_account_with_profile(db_session)
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    db_session.commit()

    with pytest.raises(
        AccountManualInterventionRequiredError,
        match="^account requires manual intervention$",
    ):
        AccountEditingRepository(db_session).validate_account_for_job(account_id=account.id)


def test_validate_account_for_job_raises_typed_runtime_unusable_error(db_session) -> None:
    class RuntimeBrokenAdapter:
        def inspect_runtime(self, account_id: str) -> dict[str, Any]:
            return {
                "account_state": AccountState.AUTHORIZED_READY,
                "runtime_health": "missing_session",
                "ok": False,
            }

    account = seed_account_with_profile(db_session)

    with pytest.raises(AccountRuntimeUnusableError, match="^account is not execution_usable$"):
        AccountEditingRepository(db_session).validate_account_for_job(
            account_id=account.id,
            execution_adapter=RuntimeBrokenAdapter(),
        )


def test_get_asset_returns_none_for_missing_asset(db_session) -> None:
    assert AccountEditingRepository(db_session).get_asset(asset_id="missing") is None


def test_find_active_duplicate_job_delegates_to_existing_duplicate_logic(db_session) -> None:
    account = seed_account_with_profile(db_session)
    repo = AccountEditingRepository(db_session)
    job = _queued_account_update_job(account.id, account.workspace_id)
    db_session.add(job)
    db_session.commit()

    duplicate = repo.find_active_duplicate_job(
        account_id=account.id,
        intent_hash=job.execution_intent_hash,
    )

    assert duplicate is not None
    assert duplicate.id == job.id


def test_finalize_job_creation_persists_expected_job_fields(db_session) -> None:
    account = seed_account_with_profile(db_session)
    repo = AccountEditingRepository(db_session)
    job = _queued_account_update_job(account.id, account.workspace_id)

    saved = repo.finalize_job_creation(
        job,
        requested_by_user_id=None,
        request_id="request-1",
        log_event_name="account_update_job_created",
    )

    assert saved.id == job.id
    assert saved.workflow_type == "account_update"
    assert saved.workflow_version == 1
    assert saved.job_payload_version == 2
    assert saved.job_state == JobState.QUEUED


def test_check_workspace_job_limit_delegates_to_workspace_limit_logic(
    db_session, monkeypatch
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_check_workspace_limit(session, workspace_id: str, limit_name: str) -> None:
        assert session is db_session
        calls.append((workspace_id, limit_name))

    monkeypatch.setattr(
        "app.modules.account_editing.repository.check_workspace_limit",
        fake_check_workspace_limit,
    )

    AccountEditingRepository(db_session).check_workspace_job_limit("workspace-1")

    assert calls == [("workspace-1", "jobs_per_day")]
