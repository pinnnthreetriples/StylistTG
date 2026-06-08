import pytest

from app.job_queue.workflows import enqueue_workflow, resolve_handler
from app.modules.contracts import WorkflowArgsMode, WorkflowSpec


class FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict[str, object]] = []

    def enqueue_call(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_handler_path_resolves_lazily() -> None:
    handler = resolve_handler("app.modules.account_editing.jobs:run_account_update_job")

    assert callable(handler)
    assert handler.__name__ == "run_account_update_job"


@pytest.mark.parametrize(
    ("handler_path", "error_type"),
    [
        ("missing_colon_path", ValueError),
        ("unknown.module:function", ModuleNotFoundError),
        ("app.modules.account_editing.jobs:missing_function", AttributeError),
    ],
)
def test_resolve_handler_rejects_invalid_handler_paths(
    handler_path: str, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        resolve_handler(handler_path)


def test_enqueue_workflow_uses_job_id_args_mode(monkeypatch) -> None:
    queues: list[FakeQueue] = []

    monkeypatch.setattr(
        "app.job_queue.workflows.get_queue",
        lambda name: queues.append(FakeQueue(name)) or queues[-1],
    )

    assert enqueue_workflow(workflow_type="account_update", job_id="job-1") is True

    assert queues[0].calls[0]["args"] == ("job-1",)
    assert queues[0].calls[0]["job_id"] == "job-1"


def test_enqueue_workflow_uses_no_args_mode_for_warmup(monkeypatch) -> None:
    queues: list[FakeQueue] = []

    monkeypatch.setattr(
        "app.job_queue.workflows.get_queue",
        lambda name: queues.append(FakeQueue(name)) or queues[-1],
    )

    assert enqueue_workflow(workflow_type="warmup_due_sessions", job_id="warmup-due-sessions")
    assert enqueue_workflow(workflow_type="warmup_dispatch_tick", job_id="warmup-dispatch-tick")

    assert queues[0].calls[0]["args"] == ()
    assert queues[1].calls[0]["args"] == ()


def test_bootstrap_channel_health_check_workflow_is_registered(monkeypatch) -> None:
    queues: list[FakeQueue] = []

    monkeypatch.setattr(
        "app.job_queue.workflows.get_queue",
        lambda name: queues.append(FakeQueue(name)) or queues[-1],
    )

    assert enqueue_workflow(
        workflow_type="warmup_bootstrap_channel_health_check",
        job_id="warmup-bootstrap-channel-health-check",
    )

    assert queues[0].calls[0]["args"] == ()


def test_enqueue_workflow_allows_explicit_custom_args(monkeypatch) -> None:
    queues: list[FakeQueue] = []

    monkeypatch.setattr(
        "app.job_queue.workflows.get_queue",
        lambda name: queues.append(FakeQueue(name)) or queues[-1],
    )

    assert enqueue_workflow(
        workflow_type="account_update",
        job_id="job-1",
        args=("explicit",),
        kwargs={"source": "test"},
        unique=False,
    )

    assert queues[0].calls[0]["args"] == ("explicit",)
    assert queues[0].calls[0]["kwargs"] == {"source": "test"}
    assert queues[0].calls[0]["unique"] is False


def test_workflow_args_mode_exports_custom_for_future_modules() -> None:
    assert WorkflowArgsMode.CUSTOM.value == "custom"


def test_custom_args_mode_requires_explicit_args(monkeypatch) -> None:
    spec = WorkflowSpec(
        workflow_type="custom",
        queue_name="profile_jobs",
        handler_path="app.modules.account_editing.jobs:run_account_update_job",
        args_mode=WorkflowArgsMode.CUSTOM,
        description="Custom args workflow.",
    )
    monkeypatch.setattr("app.job_queue.workflows.get_workflow_spec", lambda workflow_type: spec)

    with pytest.raises(ValueError, match="custom workflow args must be provided"):
        enqueue_workflow(workflow_type="custom", job_id="job-1")
