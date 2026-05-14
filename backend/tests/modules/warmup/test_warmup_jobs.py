from __future__ import annotations

import inspect

import pytest

from app.modules.warmup import dispatcher, jobs, worker


def test_module_due_sessions_job_is_no_arg_and_returns_processor_count(monkeypatch) -> None:
    calls: list[tuple[object, str]] = []

    def process_due_warmup_sessions(session, *, worker_id: str) -> int:
        calls.append((session, worker_id))
        return 3

    class SessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(jobs, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(worker, "process_due_warmup_sessions", process_due_warmup_sessions)
    monkeypatch.setattr(jobs.socket, "gethostname", lambda: "host")
    monkeypatch.setattr(jobs.os, "getpid", lambda: 123)

    assert len(inspect.signature(jobs.run_warmup_due_sessions).parameters) == 0
    assert jobs.run_warmup_due_sessions() == 3
    assert calls == [("session", "host:123")]


def test_module_dispatch_tick_job_is_no_arg_and_returns_processor_count(monkeypatch) -> None:
    calls: list[tuple[object, str]] = []

    def process_due_warmup_dispatches(session, *, worker_id: str) -> int:
        calls.append((session, worker_id))
        return 5

    class SessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(jobs, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(dispatcher, "process_due_warmup_dispatches", process_due_warmup_dispatches)
    monkeypatch.setattr(jobs.socket, "gethostname", lambda: "host")
    monkeypatch.setattr(jobs.os, "getpid", lambda: 123)

    assert len(inspect.signature(jobs.run_warmup_dispatch_tick).parameters) == 0
    assert jobs.run_warmup_dispatch_tick() == 5
    assert calls == [("session", "host:123")]


def test_legacy_worker_entrypoints_delegate_to_module_jobs(monkeypatch) -> None:
    from app.workers import warmup_dispatch_jobs, warmup_jobs

    monkeypatch.setattr(jobs, "run_warmup_due_sessions", lambda: 7)
    monkeypatch.setattr(jobs, "run_warmup_dispatch_tick", lambda: 11)

    assert warmup_jobs.run_warmup_due_sessions() == 7
    assert warmup_dispatch_jobs.run_warmup_dispatch_tick() == 11


def test_warmup_job_handlers_reject_job_id_arguments() -> None:
    with pytest.raises(TypeError):
        jobs.run_warmup_due_sessions("job-1")  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        jobs.run_warmup_dispatch_tick("job-1")  # type: ignore[call-arg]
