from app.job_queue import rq


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
    monkeypatch.setattr(rq, "Queue", lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1])

    assert rq.enqueue_profile_job("job-1") is True
    assert rq.enqueue_account_update_job("job-2") is True

    assert [queue.name for queue in queues] == [rq.PROFILE_QUEUE_NAME, rq.PROFILE_QUEUE_NAME]


def test_auth_batch_start_uses_auth_queue(monkeypatch) -> None:
    queues: list[FakeQueue] = []
    monkeypatch.setattr(rq.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(rq, "Queue", lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1])

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
    monkeypatch.setattr(rq, "Queue", lambda name, connection: queues.append(FakeQueue(name, connection)) or queues[-1])
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
