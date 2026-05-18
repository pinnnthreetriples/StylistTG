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


@pytest.mark.parametrize(
    ("role_name", "queue_name"),
    [
        ("maintenance_worker", "maintenance_jobs"),
        ("media_worker", "media_jobs"),
        ("story_worker", "story_jobs"),
        ("account_lifecycle_worker", "account_lifecycle_jobs"),
    ],
)
def test_worker_role_validation_accepts_matching_reserved_queue(
    monkeypatch: pytest.MonkeyPatch, role_name: str, queue_name: str
) -> None:
    worker_calls: list[list[str]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_worker", "--queues", queue_name, "--role", role_name],
    )
    monkeypatch.setattr(run_worker, "init_worker_observability", lambda: None)
    monkeypatch.setattr(run_worker, "get_queue", lambda name: name)
    monkeypatch.setattr(run_worker, "Redis", SimpleNamespace(from_url=lambda _url: object()))
    monkeypatch.setattr(
        run_worker,
        "SimpleWorker",
        lambda queues, connection: SimpleNamespace(work=lambda: worker_calls.append(list(queues))),
    )

    run_worker.main()

    assert worker_calls == [[queue_name]]


def test_worker_role_validation_rejects_cross_role_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_worker", "--queues", "media_jobs", "--role", "maintenance_worker"],
    )
    monkeypatch.setattr(run_worker, "init_worker_observability", lambda: None)

    with pytest.raises(ValueError, match="runtime role maintenance_worker cannot consume"):
        run_worker.main()


def test_worker_raw_queue_mode_still_accepts_reserved_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_validations: list[str] = []
    role_validations: list[tuple[str, str]] = []
    worker_calls: list[list[str]] = []

    monkeypatch.setattr(sys, "argv", ["run_worker", "--queues", "media_jobs"])
    monkeypatch.setattr(run_worker, "init_worker_observability", lambda: None)
    monkeypatch.setattr(
        run_worker,
        "assert_queue_allowed",
        lambda queue_name: queue_validations.append(queue_name),
    )
    monkeypatch.setattr(
        run_worker,
        "assert_runtime_role_allows_queue",
        lambda role_name, queue_name: role_validations.append((role_name, queue_name)),
    )
    monkeypatch.setattr(run_worker, "get_queue", lambda name: name)
    monkeypatch.setattr(run_worker, "Redis", SimpleNamespace(from_url=lambda _url: object()))
    monkeypatch.setattr(
        run_worker,
        "SimpleWorker",
        lambda queues, connection: SimpleNamespace(work=lambda: worker_calls.append(list(queues))),
    )

    run_worker.main()

    assert queue_validations == ["media_jobs"]
    assert role_validations == []
    assert worker_calls == [["media_jobs"]]


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
