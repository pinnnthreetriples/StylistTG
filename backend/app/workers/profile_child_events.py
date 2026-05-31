from __future__ import annotations

import json
import queue
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.orm import Session

from app.logging_utils import log_event
from app.models import Job, JobState
from app.services.journal import (
    mark_started_steps_uncertain,
    mark_terminal,
    record_step_failed,
    record_step_started,
    record_step_succeeded,
    record_step_uncertain,
)
from app.services.locks import heartbeat_lock
from app.services.secret_redaction import redact_text
from app.services.step_policy import is_hard_stop_error
from app.workers.profile_child_results import _ChildRunResult


@dataclass
class _ChildEventState:
    runtime_failed: bool = False
    hard_stop_error_code: str | None = None


_ChildEventHandler = Callable[[Session, Job, dict[str, Any], int, _ChildEventState], None]


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
    handler = _CHILD_EVENT_HANDLERS.get(str(event["event"]))
    if handler is not None:
        handler(session, job, event, lock_epoch, state)


def _record_step_started_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
    del state
    record_step_started(session, job, event)
    _log_step_event("step_started", job, event, lock_epoch)


def _record_step_succeeded_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
    del state
    record_step_succeeded(session, job, event)
    _log_step_event("step_succeeded", job, event, lock_epoch)


def _record_step_uncertain_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
    del state
    record_step_uncertain(session, job, event)
    _log_step_event("step_uncertain", job, event, lock_epoch, runtime_state=job.job_state)


def _record_step_failed_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
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


def _record_runtime_failed_child_event(
    session: Session,
    job: Job,
    event: dict[str, Any],
    lock_epoch: int,
    state: _ChildEventState,
) -> None:
    del session, job, lock_epoch
    state.runtime_failed = True
    state.hard_stop_error_code = _updated_hard_stop_code(
        state.hard_stop_error_code, event.get("error_code")
    )


_CHILD_EVENT_HANDLERS: dict[str, _ChildEventHandler] = {
    "step_started": _record_step_started_child_event,
    "step_succeeded": _record_step_succeeded_child_event,
    "step_uncertain": _record_step_uncertain_child_event,
    "step_failed": _record_step_failed_child_event,
    "runtime_failed": _record_runtime_failed_child_event,
}


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
    if isinstance(error_code, str) and is_hard_stop_error(error_code):
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
