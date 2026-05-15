from __future__ import annotations

from app.modules.account_editing import enqueue


def test_enqueue_account_update_job_delegates_to_workflow_registry(monkeypatch) -> None:
    enqueued: list[tuple[str, str]] = []

    def enqueue_workflow(*, workflow_type: str, job_id: str) -> bool:
        enqueued.append((workflow_type, job_id))
        return True

    monkeypatch.setattr(enqueue.workflows, "enqueue_workflow", enqueue_workflow)

    assert enqueue.enqueue_account_update_job("job-1") is True
    assert enqueued == [("account_update", "job-1")]


def test_reenqueue_account_update_job_with_delay_delegates_to_workflow_registry(
    monkeypatch,
) -> None:
    reenqueued: list[tuple[str, str, int]] = []

    def reenqueue_workflow_with_delay(
        *, workflow_type: str, job_id: str, delay_seconds: int
    ) -> bool:
        reenqueued.append((workflow_type, job_id, delay_seconds))
        return True

    monkeypatch.setattr(
        enqueue.workflows,
        "reenqueue_workflow_with_delay",
        reenqueue_workflow_with_delay,
    )

    assert enqueue.reenqueue_account_update_job_with_delay("job-1", delay_seconds=30) is True
    assert reenqueued == [("account_update", "job-1", 30)]
