from __future__ import annotations

from app.job_queue import rq


def test_enqueue_warmup_due_sessions_delegates_to_workflow_registry(monkeypatch) -> None:
    enqueued: list[tuple[str, str]] = []

    def enqueue_workflow(*, workflow_type: str, job_id: str) -> bool:
        enqueued.append((workflow_type, job_id))
        return True

    monkeypatch.setattr("app.job_queue.workflows.enqueue_workflow", enqueue_workflow)

    assert rq.enqueue_warmup_due_sessions() is True
    assert enqueued == [("warmup_due_sessions", "warmup-due-sessions")]


def test_enqueue_warmup_dispatch_tick_delegates_to_workflow_registry(monkeypatch) -> None:
    enqueued: list[tuple[str, str]] = []

    def enqueue_workflow(*, workflow_type: str, job_id: str) -> bool:
        enqueued.append((workflow_type, job_id))
        return True

    monkeypatch.setattr("app.job_queue.workflows.enqueue_workflow", enqueue_workflow)
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_min_seconds", 0)
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_max_seconds", 0)

    assert rq.enqueue_warmup_dispatch_tick() is True
    assert enqueued == [("warmup_dispatch_tick", "warmup-dispatch-tick")]


def test_enqueue_warmup_due_sessions_propagates_workflow_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.job_queue.workflows.enqueue_workflow", lambda **kwargs: False)

    assert rq.enqueue_warmup_due_sessions() is False


def test_enqueue_warmup_dispatch_tick_propagates_workflow_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.job_queue.workflows.enqueue_workflow", lambda **kwargs: False)
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_min_seconds", 0)
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_max_seconds", 0)

    assert rq.enqueue_warmup_dispatch_tick() is False
