from __future__ import annotations

# pyright: reportPrivateUsage=false, reportArgumentType=false

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TextIO

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_utils import log_event
from app.models import Job, JobState, TERMINAL_JOB_STATES, utc_now
from app.services.jobs import get_job
from app.services.journal import mark_job_running
from app.services.locks import acquire_account_lock, heartbeat_lock, release_account_lock
from app.services.tenant_scope import assert_job_account_workspace_consistency
from app.workers.profile_child_events import _run_child_event_loop
from app.workers.profile_child_results import _finalize_child_result


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
    if _reject_workspace_account_mismatch(session, job, job_id):
        return 1

    owner = f"worker:{os.getpid()}:{job_id}"
    log_event("worker_start", account_id=job.account_id, job_id=job_id, owner=owner)
    lock_epoch = acquire_account_lock(session, job.account_id, owner)
    if lock_epoch is None:
        return _handle_lock_contention(session, job, job_id)

    mark_job_running(session, job, owner=owner, lock_epoch=lock_epoch)
    heartbeat_lock(session, job.account_id, owner, lock_epoch)
    return _run_profile_child_process(session, job, job_id, owner, lock_epoch)


def _reject_workspace_account_mismatch(session: Session, job: Job, job_id: str) -> bool:
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
        return True
    return False


def _run_profile_child_process(
    session: Session, job: Job, job_id: str, owner: str, lock_epoch: int
) -> int:
    plan_path = _write_profile_plan_file(job)
    process = _launch_profile_child_process(job_id, plan_path)
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
        stdout_thread = _start_stream_reader(process.stdout, stdout_lines)
        stderr_thread = _start_stream_reader(process.stderr, stderr_lines)
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
        _close_child_process_streams(process)
        if stdout_thread is not None:
            stdout_thread.join(timeout=0.05)
        if stderr_thread is not None:
            stderr_thread.join(timeout=0.05)
        release_account_lock(session, job.account_id, owner, lock_epoch)
        Path(plan_path).unlink(missing_ok=True)


def _write_profile_plan_file(job: Job) -> str:
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
        return handle.name


def _launch_profile_child_process(job_id: str, plan_path: str) -> subprocess.Popen[str]:
    script_path = Path(__file__).resolve().parents[1] / "tdlib_job.py"
    backend_root = str(Path(__file__).resolve().parents[2])
    child_env = os.environ.copy()
    existing_pythonpath = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = (
        f"{backend_root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else backend_root
    )

    return subprocess.Popen(
        [sys.executable, str(script_path), job_id, "--plan-file", plan_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=child_env,
    )


def _start_stream_reader(
    stream: TextIO | None, stream_lines: queue.Queue[str | None]
) -> threading.Thread:
    thread = threading.Thread(target=_read_stream, args=(stream, stream_lines), daemon=True)
    thread.start()
    return thread


def _read_stream(stream: TextIO | None, stream_lines: queue.Queue[str | None]) -> None:
    if stream is None:
        stream_lines.put(None)
        return
    for output_line in stream:
        stream_lines.put(output_line)
    stream_lines.put(None)


def _close_child_process_streams(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdout, process.stderr):
        close = getattr(stream, "close", None)
        if callable(close):
            close()


# Public RQ entrypoint name expected by job_queue.rq and worker tests.
run_profile_job = execute_profile_job


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
