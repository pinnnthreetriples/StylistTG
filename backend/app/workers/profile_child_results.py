from __future__ import annotations

# pyright: reportUnusedFunction=false

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import classify_job_outcome
from app.logging_utils import log_event
from app.models import Account, AccountState, Job, JobState, utc_now
from app.services.journal import mark_started_steps_uncertain, mark_terminal
from app.services.profile_sync import build_profile_sync_adapter, sync_account_profile_state
from app.services.step_policy import classify_account_update_job_outcome


@dataclass(frozen=True)
class _ChildRunResult:
    return_code: int
    runtime_failed: bool
    hard_stop_error_code: str | None
    stderr_summary: str | None
    terminal_handled: bool = False


def _finalize_child_result(
    session: Session, job: Job, owner: str, lock_epoch: int, child_result: _ChildRunResult
) -> None:
    if child_result.return_code == 0 and not child_result.runtime_failed:
        _mark_successful_child_result(session, job, owner, lock_epoch)
    elif child_result.return_code == 3:
        _mark_uncertain_child_result(session, job, owner, lock_epoch)
    elif child_result.return_code == 2:
        _mark_interrupted_child_result(session, job, owner, lock_epoch, child_result.stderr_summary)
    elif child_result.hard_stop_error_code:
        _mark_hard_stop_child_result(session, job, owner, lock_epoch, child_result)
    elif job.workflow_type == "account_update":
        _mark_account_update_runtime_failure(session, job, owner, lock_epoch, child_result)
    else:
        _mark_profile_runtime_failure(session, job, owner, lock_epoch, child_result.stderr_summary)


def _mark_successful_child_result(session: Session, job: Job, owner: str, lock_epoch: int) -> None:
    state = _classify_terminal_job_outcome(job)
    failure_reason = None if state == JobState.COMPLETED else "profile_execution_uncertain"
    _mark_job_terminal(session, job, owner, lock_epoch, state, failure_reason=failure_reason)
    _sync_profile_state_after_job(session, job.account_id, state)


def _mark_uncertain_child_result(session: Session, job: Job, owner: str, lock_epoch: int) -> None:
    state = _classify_terminal_job_outcome(job)
    _mark_job_terminal(
        session, job, owner, lock_epoch, state, failure_reason="profile_execution_uncertain"
    )
    _sync_profile_state_after_job(session, job.account_id, state)


def _mark_interrupted_child_result(
    session: Session, job: Job, owner: str, lock_epoch: int, stderr_summary: str | None
) -> None:
    mark_started_steps_uncertain(session, job, "worker_or_child_interrupted")
    _mark_job_terminal(
        session,
        job,
        owner,
        lock_epoch,
        JobState.MANUAL_INTERVENTION_NEEDED,
        failure_reason="child_process_interrupted",
        child_stderr=stderr_summary,
    )


def _mark_hard_stop_child_result(
    session: Session, job: Job, owner: str, lock_epoch: int, child_result: _ChildRunResult
) -> None:
    assert child_result.hard_stop_error_code is not None
    _mark_account_hard_stopped(session, job.account, child_result.hard_stop_error_code)
    _mark_job_terminal(
        session,
        job,
        owner,
        lock_epoch,
        JobState.MANUAL_INTERVENTION_NEEDED,
        failure_reason=f"tdlib_hard_stop:{child_result.hard_stop_error_code}",
        recovery_marker=f"tdlib_hard_stop:{child_result.hard_stop_error_code}",
        child_stderr=child_result.stderr_summary,
    )


def _mark_account_update_runtime_failure(
    session: Session, job: Job, owner: str, lock_epoch: int, child_result: _ChildRunResult
) -> None:
    state = classify_account_update_job_outcome(
        [
            {"step_key": step.step_key, "step_type": step.step_type, "status": step.status}
            for step in job.step_results
        ]
    )
    _mark_job_terminal(
        session,
        job,
        owner,
        lock_epoch,
        state,
        failure_reason="account_update_partially_completed"
        if state == JobState.PARTIALLY_COMPLETED
        else "profile_runtime_failed",
        child_stderr=child_result.stderr_summary,
    )
    _sync_profile_state_after_job(session, job.account_id, state)


def _mark_profile_runtime_failure(
    session: Session, job: Job, owner: str, lock_epoch: int, stderr_summary: str | None
) -> None:
    mark_started_steps_uncertain(session, job, "child_process_failed")
    _mark_job_terminal(
        session,
        job,
        owner,
        lock_epoch,
        JobState.FAILED,
        failure_reason="profile_runtime_failed",
        child_stderr=stderr_summary,
    )


def _mark_job_terminal(
    session: Session,
    job: Job,
    owner: str,
    lock_epoch: int,
    state: JobState,
    *,
    failure_reason: str | None,
    child_stderr: str | None = None,
    recovery_marker: str | None = None,
) -> None:
    mark_terminal(
        session,
        job,
        state=state,
        owner=owner,
        lock_epoch=lock_epoch,
        failure_reason=failure_reason,
    )
    log_event(
        "job_terminal",
        account_id=job.account_id,
        job_id=job.id,
        lock_epoch=lock_epoch,
        runtime_state=state,
        child_stderr=child_stderr,
        recovery_marker=recovery_marker,
    )


def _classify_terminal_job_outcome(job: Job) -> JobState:
    step_results: list[dict[str, Any]] = [
        {"step_key": step.step_key, "step_type": step.step_type, "status": step.status}
        for step in job.step_results
    ]
    if job.workflow_type == "account_update":
        return classify_account_update_job_outcome(step_results)
    return classify_job_outcome(step_results)


def _sync_profile_state_after_job(session: Session, account_id: str, state: JobState) -> None:
    if state not in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}:
        return
    try:
        sync_account_profile_state(
            session,
            account_id,
            adapter=build_profile_sync_adapter(),
        )
    except Exception as exc:
        log_event(
            "profile_sync_skipped",
            account_id=account_id,
            error_class=exc.__class__.__name__,
        )


def _mark_account_hard_stopped(session: Session, account: Account, error_code: str) -> None:
    marker = f"tdlib_hard_stop:{error_code.upper()}"
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    account.runtime_state.runtime_health = "manual_intervention_needed"
    account.runtime_state.reauth_required = True
    account.runtime_state.recovery_marker = marker
    account.runtime_state.updated_at = utc_now()
    session.commit()
