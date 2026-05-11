from app.models import JobState, StepStatus
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.services.recovery import recover_interrupted_jobs
from app.workers.profile_jobs import execute_profile_job


def test_worker_subprocess_writes_step_journal(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
        },
    )

    exit_code = execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED
    assert [step.status for step in job.step_results] == [
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
    ]


def test_failed_step_persists_journal_and_terminal_state(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
            "mock_fail_step": "set_username",
        },
    )

    exit_code = execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    failed = [step for step in job.step_results if step.status == StepStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].step_type == "set_username"


def test_recovery_marks_started_step_uncertain_without_blind_resume(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
            "mock_crash_after_step_started": "set_bio",
        },
    )

    exit_code = execute_profile_job(job.id, session=db_session)
    recover_interrupted_jobs(db_session)

    db_session.refresh(job)
    assert exit_code == 2
    assert job.job_state == JobState.MANUAL_INTERVENTION_NEEDED
    uncertain = [step for step in job.step_results if step.status == StepStatus.UNCERTAIN]
    assert len(uncertain) == 1
    assert uncertain[0].step_type == "set_bio"
    assert uncertain[0].uncertain_reason == "worker_or_child_interrupted"
