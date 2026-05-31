from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Account, AccountState, Job, JobState, TERMINAL_JOB_STATES, utc_now
from app.adapters.tdlib_profile_execution import classify_job_outcome
from app.logging_utils import log_event
from app.services.journal import (
    mark_job_running,
    mark_started_steps_uncertain,
    mark_terminal,
    record_step_failed,
    record_step_started,
    record_step_succeeded,
    record_step_uncertain,
)
from app.services.jobs import get_job
from app.services.locks import acquire_account_lock, heartbeat_lock, release_account_lock
from app.services.profile_sync import build_profile_sync_adapter, sync_account_profile_state
from app.services.secret_redaction import redact_text
from app.services.step_policy import classify_account_update_job_outcome, is_hard_stop_error
from app.services.tenant_scope import assert_job_account_workspace_consistency


@dataclass
class _ChildEventState:
    runtime_failed: bool = False
    hard_stop_error_code: str | None = None


@dataclass(frozen=True)
class _ChildRunResult:
    return_code: int
    runtime_failed: bool
    hard_stop_error_code: str | None
    stderr_summary: str | None
    terminal_handled: bool = False


def execute_profile_job(job_id: str, *, session: Session | None = None) -> int:
    owns_session = session is None
    db_session = session or SessionLocal()
    try:
        return _execute_profile_job(job_id, db_session)
    finally:
        if owns_session:
            db_session.close()


def _execute_profile_job(job_id: str, session: Session) -> int:
    job = get_job(session, job_id)
    if job is None:
        return 1
    if job.job_state in TERMINAL_JOB_STATES:
        log_event(
            "worker_skip_terminal_job",
            account_id=job.account_id,
            job_id=job_id,
            state=job.job_state,
        )
        return 0
    try:
        assert_job_account_workspace_consistency(job)
    except ValueError:
        job.job_state = JobState.FAILED
        job.failure_reason = "workspace_account_mismatch"
        job.finished_at = utc_now()
        session.commit()
        log_event(
            "worker_reject_workspace_account_mismatch", account_id=job.account_id, job_id=job_id
        )
        return 1

    owner = f"worker:{os.getpid()}:{job_id}"
    log_event("worker_start", account_id=job.account_id, job_id=job_id, owner=owner)
    lock_epoch = acquire_account_lock(session, job.account_id, owner)
    if lock_epoch is None:
        return _handle_lock_contention(session, job, job_id)

    mark_job_running(session, job, owner=owner, lock_epoch=lock_epoch)
    heartbeat_lock(session, job.account_id, owner, lock_epoch)

    script_path = Path(__file__).resolve().parents[1] / "tdlib_job.py"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(
            {
                "account_id": job.account_id,
                "plan_json_snapshot": job.plan_json_snapshot,
                "payload_json": job.payload_json,
            },
            handle,
            sort_keys=True,
        )
        plan_path = handle.name

    backend_root = str(Path(__file__).resolve().parents[2])
    child_env = os.environ.copy()
    existing_pythonpath = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = (
        f"{backend_root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else backend_root
    )

    process = subprocess.Popen(
        [sys.executable, str(script_path), job_id, "--plan-file", plan_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=child_env,
    )
    log_event(
        "subprocess_launch",
        account_id=job.account_id,
        job_id=job_id,
        lock_epoch=lock_epoch,
        adapter=settings.profile_execution_adapter,
    )
    stdout_thread: threading.Thread | None = None
    stderr_thread: threading.Thread | None = None
    try:
        assert process.stdout is not None
        deadline = time.monotonic() + settings.profile_job_timeout_seconds
        stdout_lines: queue.Queue[str | None] = queue.Queue()
        stderr_lines: queue.Queue[str | None] = queue.Queue()
        stderr_buffer: list[str] = []

        def read_stdout() -> None:
            assert process.stdout is not None
            for output_line in process.stdout:
                stdout_lines.put(output_line)
            stdout_lines.put(None)

        def read_stderr() -> None:
            stderr = process.stderr
            if stderr is None:
                stderr_lines.put(None)
                return
            for output_line in stderr:
                stderr_lines.put(output_line)
            stderr_lines.put(None)

        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        child_result = _run_child_event_loop(
            session,
            job,
            process=process,
            owner=owner,
            lock_epoch=lock_epoch,
            deadline=deadline,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            stderr_buffer=stderr_buffer,
        )
        if child_result.terminal_handled:
            return child_result.return_code
        session.refresh(job)
        _finalize_child_result(session, job, owner, lock_epoch, child_result)
        return child_result.return_code
    finally:
        for stream in (process.stdout, process.stderr):
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        if stdout_thread is not None:
            stdout_thread.join(timeout=0.05)
        if stderr_thread is not None:
            stderr_thread.join(timeout=0.05)
        release_account_lock(session, job.account_id, owner, lock_epoch)
        Path(plan_path).unlink(missing_ok=True)


def _run_child_event_loop(
    session: Session,
    job: Job,
    *,
    process: subprocess.Popen[str],
    owner: str,
    lock_epoch: int,
    deadline: float,
    stdout_lines: queue.Queue[str | None],
    stderr_lines: queue.Queue[str | None],
    stderr_buffer: list[str],
) -> _ChildRunResult:
    state = _ChildEventState()
    while True:
        _drain_stderr(stderr_lines, stderr_buffer)
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            _mark_child_process_timeout(
                session,
                job,
                process,
                owner,
                lock_epoch,
                stderr_summary=_stderr_summary(stderr_buffer),
            )
            return _ChildRunResult(1, state.runtime_failed, state.hard_stop_error_code, None, True)
        line = _read_child_stdout(stdout_lines, remaining_seconds)
        if line is None:
            break
        if line == "":
            continue
        if not _handle_child_output_line(session, job, owner, lock_epoch, line, state):
            return _ChildRunResult(1, state.runtime_failed, state.hard_stop_error_code, None, True)
    return _wait_for_child_process(
        session,
        job,
        process=process,
        owner=owner,
        lock_epoch=lock_epoch,
        deadline=deadline,
        stderr_lines=stderr_lines,
        stderr_buffer=stderr_buffer,
        state=state,
    )


def _read_child_stdout(
    stdout_lines: queue.Queue[str | None], remaining_seconds: float
) -> str | None:
    try:
        line = stdout_lines.get(timeout=min(0.2, remaining_seconds))
    except queue.Empty:
        return ""
    return line


def _handle_child_output_line(
    session: Session,
    job: Job,
    owner: str,
    lock_epoch: int,
    line: str,
    state: _ChildEventState,
) -> bool:
    try:
        event = cast(dict[str, Any], json.loads(line))
    except json.JSONDecodeError:
        _mark_malformed_child_event(session, job, owner, lock_epoch)
        return False
    heartbeat_lock(session, job.account_id, owner, lock_epoch)
    _record_child_event(session, job, event, lock_epoch, state)
    return True


def _mark_malformed_child_event(session: Session, job: Job, owner: str, lock_epoch: int) -> None:
    mark_terminal(
        session,
        job,
        state=JobState.FAILED,
        owner=owner,
        lock_epoch=lock_epoch,
        failure_reason="malformed_child_event",
    )
    log_event(
        "subprocess_malformed_event",
        account_id=job.account_id,
        job_id=job.id,
        lock_epoch=lock_epoch,
    )


def _record_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
    event_name = event["event"]
    if event_name == "step_started":
        record_step_started(session, job, event)
        _log_step_event("step_started", job, event, lock_epoch)
    elif event_name == "step_succeeded":
        record_step_succeeded(session, job, event)
        _log_step_event("step_succeeded", job, event, lock_epoch)
    elif event_name == "step_uncertain":
        record_step_uncertain(session, job, event)
        _log_step_event("step_uncertain", job, event, lock_epoch, runtime_state=job.job_state)
    elif event_name == "step_failed":
        state.runtime_failed = True
        state.hard_stop_error_code = _updated_hard_stop_code(
            state.hard_stop_error_code, event.get("error_code")
        )
        record_step_failed(session, job, event)
        _log_step_event(
            "step_failed",
            job,
            event,
            lock_epoch,
            error_class=event.get("error_class"),
            error_code=event.get("error_code"),
        )
    elif event_name == "runtime_failed":
        state.runtime_failed = True
        state.hard_stop_error_code = _updated_hard_stop_code(
            state.hard_stop_error_code, event.get("error_code")
        )


def _log_step_event(
    event_name: str,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    **extra: Any,
) -> None:
    log_event(
        event_name,
        account_id=job.account_id,
        job_id=job.id,
        step_key=event["step_key"],
        lock_epoch=lock_epoch,
        **extra,
    )


def _updated_hard_stop_code(current: str | None, error_code: object) -> str | None:
    if isinstance(error_code, str) and _is_tdlib_hard_stop_error(error_code):
        return error_code
    return current


def _wait_for_child_process(
    session: Session,
    job: Job,
    *,
    process: subprocess.Popen[str],
    owner: str,
    lock_epoch: int,
    deadline: float,
    stderr_lines: queue.Queue[str | None],
    stderr_buffer: list[str],
    state: _ChildEventState,
) -> _ChildRunResult:
    try:
        return_code = process.wait(timeout=max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        _mark_child_process_timeout(
            session,
            job,
            process,
            owner,
            lock_epoch,
            stderr_summary=_stderr_summary(stderr_buffer),
        )
        return _ChildRunResult(1, state.runtime_failed, state.hard_stop_error_code, None, True)
    _drain_stderr(stderr_lines, stderr_buffer)
    return _ChildRunResult(
        return_code,
        state.runtime_failed,
        state.hard_stop_error_code,
        _stderr_summary(stderr_buffer),
    )


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


def _mark_child_process_timeout(
    session: Session,
    job: Job,
    process: subprocess.Popen[str],
    owner: str,
    lock_epoch: int,
    *,
    stderr_summary: str | None = None,
) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Already SIGKILLed; let the OS reap. Job is marked terminal below.
            pass
    mark_started_steps_uncertain(session, job, "child_process_timeout")
    mark_terminal(
        session,
        job,
        state=JobState.FAILED,
        owner=owner,
        lock_epoch=lock_epoch,
        failure_reason="child_process_timeout",
    )
    log_event(
        "subprocess_timeout",
        account_id=job.account_id,
        job_id=job.id,
        lock_epoch=lock_epoch,
        child_stderr=stderr_summary,
    )


def _drain_stderr(stderr_lines: queue.Queue[str | None], stderr_buffer: list[str]) -> None:
    while True:
        try:
            line = stderr_lines.get_nowait()
        except queue.Empty:
            return
        if line is None:
            return
        stderr_buffer.append(line)
        while sum(len(item) for item in stderr_buffer) > 4096 and stderr_buffer:
            stderr_buffer.pop(0)


def _stderr_summary(stderr_buffer: list[str]) -> str | None:
    if not stderr_buffer:
        return None
    text = "".join(stderr_buffer)[-4096:]
    text = redact_text(text)
    return text.strip() or None


def run_profile_job(job_id: str) -> int:
    return execute_profile_job(job_id)


def _handle_lock_contention(session: Session, job: Job, job_id: str) -> int:
    from datetime import UTC

    queued_at = job.queued_at
    if queued_at is not None and queued_at.tzinfo is None:
        queued_at = queued_at.replace(tzinfo=UTC)
    elapsed = (utc_now() - queued_at).total_seconds() if queued_at else 0
    if elapsed > settings.max_lock_wait_seconds:
        job.job_state = JobState.FAILED
        job.finished_at = utc_now()
        job.failure_reason = "lock_wait_timeout"
        session.commit()
        log_event(
            "worker_lock_wait_timeout",
            account_id=job.account_id,
            job_id=job_id,
            elapsed_seconds=elapsed,
        )
        return 1
    job.job_state = JobState.WAITING_LOCK
    session.commit()
    _try_reenqueue(job_id, job.workflow_type)
    log_event(
        "worker_waiting_lock_retry",
        account_id=job.account_id,
        job_id=job_id,
        elapsed_seconds=elapsed,
    )
    return 1


def _try_reenqueue(job_id: str, workflow_type: str | None) -> None:
    try:
        from app.job_queue.rq import reenqueue_job_with_delay

        reenqueue_job_with_delay(
            job_id,
            delay_seconds=settings.lock_retry_delay_seconds,
            workflow_type=workflow_type,
        )
    except Exception:
        log_event("worker_reenqueue_failed", job_id=job_id)


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


def _is_tdlib_hard_stop_error(error_code: str | None) -> bool:
    return is_hard_stop_error(error_code)


def _mark_account_hard_stopped(session: Session, account: Account, error_code: str) -> None:
    marker = f"tdlib_hard_stop:{error_code.upper()}"
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    account.runtime_state.runtime_health = "manual_intervention_needed"
    account.runtime_state.reauth_required = True
    account.runtime_state.recovery_marker = marker
    account.runtime_state.updated_at = utc_now()
    session.commit()
