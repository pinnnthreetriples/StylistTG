from __future__ import annotations

import argparse

from redis import Redis
from rq import SimpleWorker

from app.config import settings
from app.job_queue.rq import get_queue
from app.services.worker_plane import assert_queue_allowed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a production queue-specific RQ worker.")
    parser.add_argument("--queues", required=True, help="Comma-separated allowlisted queues")
    args = parser.parse_args()
    queue_names = [item.strip() for item in args.queues.split(",") if item.strip()]
    if not queue_names:
        raise SystemExit("at least one queue is required")
    for queue_name in queue_names:
        assert_queue_allowed(queue_name)
    connection = Redis.from_url(settings.redis_url)
    queues = [get_queue(queue_name) for queue_name in queue_names]
    worker = SimpleWorker(queues, connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
