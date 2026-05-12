from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.config import Settings
from app.models import JobState, StepStatus
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.workers.profile_jobs import execute_profile_job

from conftest import FakeExecutionUsableAdapter, FakeProfileSyncAdapter


def _seed_profile_job(db_session, *, payload):
    """Create an execution-usable account and a profile job."""
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload=payload,
        execution_adapter=FakeExecutionUsableAdapter(),
    )
    return account, job


def test_ambiguous_username_path_becomes_uncertain_and_manual_intervention(
    db_session, storage_dir
) -> None:
    _account, job = _seed_profile_job(
        db_session,
        payload={
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
            "mock_username_verify": "mismatch",
        },
    )

    exit_code = execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 3
    assert job.job_state == JobState.MANUAL_INTERVENTION_NEEDED
    username_steps = [step for step in job.step_results if step.step_type == "set_username"]
    assert username_steps[0].status == StepStatus.UNCERTAIN
    assert username_steps[0].uncertain_reason == "username_verify_mismatch"


def test_completed_profile_job_syncs_materialized_profile_state(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.workers.profile_jobs.build_profile_sync_adapter",
        lambda: FakeProfileSyncAdapter(),
    )
    account, job = _seed_profile_job(
        db_session,
        payload={
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": None,
            "photo_asset_id": None,
        },
    )

    exit_code = execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    db_session.refresh(account)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED
    assert account.profile_state is not None
    assert account.profile_state.first_name == "King"
    assert account.profile_state.last_name == "Blackburn"
    assert account.profile_state.username == "kingblackburn"
    assert account.profile_state.bio == "Live from Telegram"


def test_tdlib_adapter_does_not_fall_back_to_mock_when_library_is_missing() -> None:
    adapter = build_profile_execution_adapter(
        Settings(
            profile_execution_adapter="tdlib",
            tdlib_shared_library_path="C:/missing/tdjson.dll",
        )
    )

    inspection = adapter.inspect_runtime("account-1")

    assert inspection["ok"] is False
    assert inspection["runtime_health"] == "tdlib_unavailable"
