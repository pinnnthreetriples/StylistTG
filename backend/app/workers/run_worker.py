from __future__ import annotations

import argparse
from contextlib import suppress

from rq import SimpleWorker

from app.job_queue.rq import get_queue
from app.observability import init_worker_observability
from app.runtime.roles import assert_runtime_role_allows_queue
from app.services.redis_client import redis_from_url
from app.services.worker_plane import assert_queue_allowed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a production queue-specific RQ worker.")
    parser.add_argument("--queues", required=True, help="Comma-separated allowlisted queues")
    parser.add_argument(
        "--role", help="Optional runtime role name used to validate queue ownership"
    )
    args = parser.parse_args()
    init_worker_observability()
    queue_names = [item.strip() for item in args.queues.split(",") if item.strip()]
    if not queue_names:
        raise SystemExit("at least one queue is required")
    for queue_name in queue_names:
        if args.role:
            assert_runtime_role_allows_queue(args.role, queue_name)
        else:
            assert_queue_allowed(queue_name)
    connection = redis_from_url()
    queues = [get_queue(queue_name) for queue_name in queue_names]
    worker = SimpleWorker(queues, connection=connection)
    try:
        worker.work()
    finally:
        _flush_observability()


def _flush_observability() -> None:
    try:
        import sentry_sdk
    except ImportError:
        return
    with suppress(Exception):
        sentry_sdk.flush(timeout=2.0)


if __name__ == "__main__":
    main()
