from __future__ import annotations

from datetime import timedelta

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry

from app.config import settings
from app.workers.auth_batch_jobs import run_batch_start_auth
from app.workers.account_update_jobs import run_account_update_job
from app.workers.profile_jobs import run_profile_job

QUEUE_NAME = "profile_jobs"


def get_profile_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(QUEUE_NAME, connection=connection)


def enqueue_profile_job(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        queue.enqueue_call(func=run_profile_job, args=(job_id,), job_id=job_id, unique=True)
    except RedisError:
        return False
    return True


def enqueue_account_update_job(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        queue.enqueue_call(func=run_account_update_job, args=(job_id,), job_id=job_id, unique=True)
    except RedisError:
        return False
    return True


def enqueue_batch_start_auth(item_id: str, attempt_count: int, *, delay_seconds: int = 0) -> bool:
    queue = get_profile_queue()
    job_id = f"auth-start-{item_id}-attempt-{attempt_count}"
    try:
        if delay_seconds > 0:
            queue.enqueue_in(
                timedelta(seconds=delay_seconds),
                run_batch_start_auth,
                args=(item_id,),
                job_id=job_id,
            )
        else:
            queue.enqueue_call(func=run_batch_start_auth, args=(item_id,), job_id=job_id, unique=True)
    except RedisError:
        return False
    return True


def remove_job_from_queue(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        queue.remove(job_id)
        for registry_cls in (DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry):
            registry = registry_cls(QUEUE_NAME, connection=queue.connection)
            if job_id in registry.get_job_ids():
                registry.remove(job_id, delete_job=True)
        try:
            Job.fetch(job_id, connection=queue.connection).delete()
        except NoSuchJobError:
            pass
    except RedisError:
        return False
    return True
