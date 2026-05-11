from app.job_queue import rq
from redis.exceptions import RedisError


class FakeQueue:
    def __init__(self, name: str, connection) -> None:
        self.name = name
        self.connection = connection
        self.calls: list[tuple[str, object, tuple, str | None]] = []

    def enqueue_call(self, *, func, args, job_id=None, unique=False):
        self.calls.append(("call", func, args, job_id))

    def enqueue_in(self, delta, func, *, args, job_id=None):
        self.calls.append(("in", func, args, job_id))

    def remove(self, job_id):
        self.calls.append(("remove", None, (), job_id))


def test_account_update_and_profile_jobs_use_profile_queue(monkeypatch) -> None:
    queues: list[FakeQueue] = []
    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(
        rq,
        "Queue",
        lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1],
    )

    assert rq.enqueue_profile_job("job-1") is True
    assert rq.enqueue_account_update_job("job-2") is True

    assert [queue.name for queue in queues] == [rq.PROFILE_QUEUE_NAME, rq.PROFILE_QUEUE_NAME]


def test_auth_batch_start_uses_auth_queue(monkeypatch) -> None:
    queues: list[FakeQueue] = []
    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(
        rq,
        "Queue",
        lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1],
    )

    assert rq.enqueue_batch_start_auth("item-1", 1) is True

    assert queues[0].name == rq.AUTH_QUEUE_NAME
    assert queues[0].calls[0][3] == "auth-start-item-1-attempt-1"


def test_remove_job_from_queue_checks_profile_and_auth_queues(monkeypatch) -> None:
    queues: list[FakeQueue] = []

    class FakeRegistry:
        def __init__(self, name, connection) -> None:
            self.name = name

        def get_job_ids(self):
            return []

    class FakeJob:
        @staticmethod
        def fetch(job_id, connection):
            raise rq.NoSuchJobError

    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(
        rq,
        "Queue",
        lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1],
    )
    monkeypatch.setattr(rq, "DeferredJobRegistry", FakeRegistry)
    monkeypatch.setattr(rq, "FailedJobRegistry", FakeRegistry)
    monkeypatch.setattr(rq, "StartedJobRegistry", FakeRegistry)
    monkeypatch.setattr(rq, "Job", FakeJob)

    assert rq.remove_job_from_queue("job-1") is True

    assert [queue.name for queue in queues] == [rq.PROFILE_QUEUE_NAME, rq.AUTH_QUEUE_NAME]
    assert [queue.calls[0] for queue in queues] == [
        ("remove", None, (), "job-1"),
        ("remove", None, (), "job-1"),
    ]


def test_enqueue_failure_logs_queue_and_job_without_secret_url(monkeypatch) -> None:
    events = []

    class FailingQueue(FakeQueue):
        def enqueue_call(self, *, func, args, job_id=None, unique=False):
            raise RedisError("redis://:secret@example.test/0")

    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(rq, "Queue", lambda name, connection: FailingQueue(name, connection))
    monkeypatch.setattr(rq, "log_warn", lambda event, **fields: events.append((event, fields)))

    assert rq.enqueue_profile_job("job-1") is False

    assert events == [
        (
            "queue_enqueue_failed",
            {"queue_name": rq.PROFILE_QUEUE_NAME, "job_id": "job-1", "error_class": "RedisError"},
        )
    ]


def test_warmup_dispatch_tick_uses_dispatch_queue(monkeypatch) -> None:
    """enqueue_warmup_dispatch_tick must route to WARMUP_DISPATCH_QUEUE_NAME, not warmup_jobs."""

    class FlexQueue(FakeQueue):
        def enqueue_call(self, *, func, args=(), job_id=None, unique=False):
            self.calls.append(("call", func, args, job_id))

    queues: list[FlexQueue] = []
    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(
        rq,
        "Queue",
        lambda name, connection: queues.append(FlexQueue(name, connection)) or queues[-1],
    )

    assert rq.enqueue_warmup_dispatch_tick() is True

    assert len(queues) == 1
    assert queues[0].name == rq.WARMUP_DISPATCH_QUEUE_NAME
    # Job id must be deterministic so back-to-back ticks coalesce via unique=True
    assert queues[0].calls[0][3] == "warmup-dispatch-tick"


def test_warmup_dispatch_queue_is_in_production_allowlist() -> None:
    """WARMUP_DISPATCH_QUEUE_NAME must be in the production queue allowlist used by run_worker."""
    from app.services.worker_plane import PRODUCTION_QUEUE_NAMES, assert_queue_allowed

    assert rq.WARMUP_DISPATCH_QUEUE_NAME in PRODUCTION_QUEUE_NAMES
    # Must not raise for a valid dispatch queue
    assert_queue_allowed(rq.WARMUP_DISPATCH_QUEUE_NAME)


def test_warmup_dispatch_tick_redis_error_returns_false(monkeypatch) -> None:
    """A Redis failure in enqueue_warmup_dispatch_tick must return False, not raise."""
    events: list = []

    class FailingQueue(FakeQueue):
        def enqueue_call(self, *, func, args=(), job_id=None, unique=False):
            raise RedisError("connection refused")

    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(rq, "Queue", lambda name, connection: FailingQueue(name, connection))
    monkeypatch.setattr(rq, "log_warn", lambda event, **fields: events.append((event, fields)))

    result = rq.enqueue_warmup_dispatch_tick()

    assert result is False
    assert events[0][0] == "queue_enqueue_failed"
    assert events[0][1]["queue_name"] == rq.WARMUP_DISPATCH_QUEUE_NAME
