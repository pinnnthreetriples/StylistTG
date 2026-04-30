from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AccountState, JobState, TERMINAL_JOB_STATES, utc_now
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
from app.services.step_policy import classify_account_update_job_outcome, is_hard_stop_error


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
        log_event("worker_skip_terminal_job", account_id=job.account_id, job_id=job_id, state=job.job_state)
        return 0

    owner = f"worker:{os.getpid()}:{job_id}"
    log_event("worker_start", account_id=job.account_id, job_id=job_id, owner=owner)
    lock_epoch = acquire_account_lock(session, job.account_id, owner)
    if lock_epoch is None:
        job.job_state = JobState.WAITING_LOCK
        session.commit()
        log_event("worker_waiting_lock", account_id=job.account_id, job_id=job_id)
        return 1

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

    process = subprocess.Popen(
        [sys.executable, str(script_path), job_id, "--plan-file", plan_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    log_event(
        "subprocess_launch",
        account_id=job.account_id,
        job_id=job_id,
        lock_epoch=lock_epoch,
        adapter=settings.profile_execution_adapter,
    )
    runtime_failed = False
    hard_stop_error_code: str | None = None
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
            if getattr(process, "stderr", None) is None:
                stderr_lines.put(None)
                return
            for output_line in process.stderr:
                stderr_lines.put(output_line)
            stderr_lines.put(None)

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        while True:
            _drain_stderr(stderr_lines, stderr_buffer)
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                _mark_child_process_timeout(session, job, process, owner, lock_epoch, stderr_summary=_stderr_summary(stderr_buffer))
                return 1
            try:
                line = stdout_lines.get(timeout=min(0.2, remaining_seconds))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
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
                    job_id=job_id,
                    lock_epoch=lock_epoch,
                )
                return 1
            heartbeat_lock(session, job.account_id, owner, lock_epoch)
            if event["event"] == "step_started":
                record_step_started(session, job, event)
                log_event(
                    "step_started",
                    account_id=job.account_id,
                    job_id=job_id,
                    step_key=event["step_key"],
                    lock_epoch=lock_epoch,
                )
            elif event["event"] == "step_succeeded":
                record_step_succeeded(session, job, event)
                log_event(
                    "step_succeeded",
                    account_id=job.account_id,
                    job_id=job_id,
                    step_key=event["step_key"],
                    lock_epoch=lock_epoch,
                )
            elif event["event"] == "step_uncertain":
                record_step_uncertain(session, job, event)
                log_event(
                    "step_uncertain",
                    account_id=job.account_id,
                    job_id=job_id,
                    step_key=event["step_key"],
                    lock_epoch=lock_epoch,
                    runtime_state=job.job_state,
                )
            elif event["event"] == "step_failed":
                runtime_failed = True
                error_code = event.get("error_code")
                if _is_tdlib_hard_stop_error(error_code):
                    hard_stop_error_code = error_code
                record_step_failed(session, job, event)
                log_event(
                    "step_failed",
                    account_id=job.account_id,
                    job_id=job_id,
                    step_key=event["step_key"],
                    lock_epoch=lock_epoch,
                    error_class=event.get("error_class"),
                    error_code=event.get("error_code"),
                )
            elif event["event"] == "runtime_failed":
                runtime_failed = True
                error_code = event.get("error_code")
                if _is_tdlib_hard_stop_error(error_code):
                    hard_stop_error_code = error_code

        try:
            return_code = process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _mark_child_process_timeout(session, job, process, owner, lock_epoch, stderr_summary=_stderr_summary(stderr_buffer))
            return 1
        _drain_stderr(stderr_lines, stderr_buffer)
        stderr_summary = _stderr_summary(stderr_buffer)
        session.refresh(job)
        if return_code == 0 and not runtime_failed:
            state = _classify_terminal_job_outcome(job)
            failure_reason = None if state == JobState.COMPLETED else "profile_execution_uncertain"
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
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=state,
            )
            _sync_profile_state_after_job(session, job.account_id, state)
        elif return_code == 3:
            state = _classify_terminal_job_outcome(job)
            mark_terminal(
                session,
                job,
                state=state,
                owner=owner,
                lock_epoch=lock_epoch,
                failure_reason="profile_execution_uncertain",
            )
            log_event(
                "job_terminal",
                account_id=job.account_id,
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=state,
            )
            _sync_profile_state_after_job(session, job.account_id, state)
        elif return_code == 2:
            mark_started_steps_uncertain(session, job, "worker_or_child_interrupted")
            mark_terminal(
                session,
                job,
                state=JobState.MANUAL_INTERVENTION_NEEDED,
                owner=owner,
                lock_epoch=lock_epoch,
                failure_reason="child_process_interrupted",
            )
            log_event(
                "job_terminal",
                account_id=job.account_id,
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=JobState.MANUAL_INTERVENTION_NEEDED,
                child_stderr=stderr_summary,
            )
        elif hard_stop_error_code:
            _mark_account_hard_stopped(session, job.account, hard_stop_error_code)
            mark_terminal(
                session,
                job,
                state=JobState.MANUAL_INTERVENTION_NEEDED,
                owner=owner,
                lock_epoch=lock_epoch,
                failure_reason=f"tdlib_hard_stop:{hard_stop_error_code}",
            )
            log_event(
                "job_terminal",
                account_id=job.account_id,
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=JobState.MANUAL_INTERVENTION_NEEDED,
                recovery_marker=f"tdlib_hard_stop:{hard_stop_error_code}",
                child_stderr=stderr_summary,
            )
        elif job.workflow_type == "account_update":
            state = classify_account_update_job_outcome(
                [
                    {"step_key": step.step_key, "step_type": step.step_type, "status": step.status}
                    for step in job.step_results
                ]
            )
            mark_terminal(
                session,
                job,
                state=state,
                owner=owner,
                lock_epoch=lock_epoch,
                failure_reason="account_update_partially_completed"
                if state == JobState.PARTIALLY_COMPLETED
                else "profile_runtime_failed",
            )
            log_event(
                "job_terminal",
                account_id=job.account_id,
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=state,
                child_stderr=stderr_summary,
            )
            _sync_profile_state_after_job(session, job.account_id, state)
        else:
            mark_started_steps_uncertain(session, job, "child_process_failed")
            mark_terminal(
                session,
                job,
                state=JobState.FAILED,
                owner=owner,
                lock_epoch=lock_epoch,
                failure_reason="profile_runtime_failed",
            )
            log_event(
                "job_terminal",
                account_id=job.account_id,
                job_id=job_id,
                lock_epoch=lock_epoch,
                runtime_state=JobState.FAILED,
                child_stderr=stderr_summary,
            )
        return return_code
    finally:
        release_account_lock(session, job.account_id, owner, lock_epoch)
        Path(plan_path).unlink(missing_ok=True)


def _mark_child_process_timeout(
    session: Session,
    job,
    process: subprocess.Popen,
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
    text = re.sub(r"(?i)(password|token|api_hash|secret)=\\S+", r"\1=***", text)
    return text.strip() or None


def run_profile_job(job_id: str) -> int:
    return execute_profile_job(job_id)


def _classify_terminal_job_outcome(job) -> JobState:
    step_results = [
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


def _mark_account_hard_stopped(session: Session, account, error_code: str) -> None:
    marker = f"tdlib_hard_stop:{error_code.upper()}"
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    account.runtime_state.runtime_health = "manual_intervention_needed"
    account.runtime_state.reauth_required = True
    account.runtime_state.recovery_marker = marker
    account.runtime_state.updated_at = utc_now()
    session.commit()
