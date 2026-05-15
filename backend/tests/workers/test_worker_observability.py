from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.workers import run_worker


def test_worker_observability_initializes_before_queue_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_queue_validation(_queue_name: str) -> None:
        calls.append("validate")
        raise ValueError("unsupported worker queue")

    monkeypatch.setattr(sys, "argv", ["run_worker", "--queues", "unsupported_jobs"])
    monkeypatch.setattr(
        run_worker,
        "init_worker_observability",
        lambda: calls.append("init") or True,
    )
    monkeypatch.setattr(run_worker, "assert_queue_allowed", fail_queue_validation)

    with pytest.raises(ValueError):
        run_worker.main()

    assert calls == ["init", "validate"]


def test_worker_role_validation_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_worker", "--queues", "warmup_dispatch_jobs", "--role", "warmup_dispatch_worker"],
    )
    monkeypatch.setattr(run_worker, "init_worker_observability", lambda: None)
    monkeypatch.setattr(
        run_worker,
        "assert_runtime_role_allows_queue",
        lambda role, queue: calls.append((role, queue)),
    )
    monkeypatch.setattr(run_worker, "get_queue", lambda queue_name: queue_name)
    monkeypatch.setattr(run_worker, "Redis", SimpleNamespace(from_url=lambda _url: object()))
    monkeypatch.setattr(
        run_worker,
        "SimpleWorker",
        lambda _queues, connection: SimpleNamespace(work=lambda: None),
    )

    run_worker.main()

    assert calls == [("warmup_dispatch_worker", "warmup_dispatch_jobs")]


def test_flush_observability_does_not_mask_worker_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentry_sdk = SimpleNamespace(
        flush=lambda timeout: (_ for _ in ()).throw(RuntimeError("flush failed"))
    )
    monkeypatch.setitem(sys.modules, "sentry_sdk", sentry_sdk)

    # Should swallow the flush RuntimeError silently — not propagate.
    result = run_worker._flush_observability()
    assert result is None
