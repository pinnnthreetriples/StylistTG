from __future__ import annotations

from datetime import timedelta

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry

from app.config import settings
from app.logging_utils import log_warn
from app.workers.auth_batch_jobs import run_batch_start_auth
from app.workers.telegram_auth_jobs import run_telegram_auth_job
from app.workers.account_update_jobs import run_account_update_job
from app.workers.warmup_jobs import run_warmup_due_sessions
from app.workers.warmup_dispatch_jobs import run_warmup_dispatch_tick
from app.workers.profile_jobs import run_profile_job
from app.services.worker_plane import (
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    AUTH_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    PROFILE_QUEUE_NAME,
    SCHEDULER_QUEUE_NAME,
    STORY_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
    PRODUCTION_QUEUE_NAMES,
)

QUEUE_NAME = PROFILE_QUEUE_NAME

__all__ = [
    "ACCOUNT_LIFECYCLE_QUEUE_NAME",
    "AUTH_QUEUE_NAME",
    "MAINTENANCE_QUEUE_NAME",
    "MEDIA_QUEUE_NAME",
    "PROFILE_QUEUE_NAME",
    "QUEUE_NAME",
    "SCHEDULER_QUEUE_NAME",
    "STORY_QUEUE_NAME",
    "WARMUP_DISPATCH_QUEUE_NAME",
    "WARMUP_QUEUE_NAME",
    "enqueue_account_update_job",
    "enqueue_batch_start_auth",
    "enqueue_telegram_auth_action",
    "enqueue_profile_job",
    "enqueue_warmup_due_sessions",
    "enqueue_warmup_dispatch_tick",
    "get_auth_queue",
    "get_profile_queue",
    "get_queue",
    "remove_job_from_queue",
]


def get_profile_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(PROFILE_QUEUE_NAME, connection=connection)


def get_auth_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(AUTH_QUEUE_NAME, connection=connection)


def get_queue(queue_name: str) -> Queue:
    if queue_name not in PRODUCTION_QUEUE_NAMES:
        raise ValueError(f"unsupported queue: {queue_name}")
    connection = Redis.from_url(settings.redis_url)
    return Queue(queue_name, connection=connection)


def enqueue_profile_job(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        queue.enqueue_call(func=run_profile_job, args=(job_id,), job_id=job_id, unique=True)
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_account_update_job(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        queue.enqueue_call(func=run_account_update_job, args=(job_id,), job_id=job_id, unique=True)
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_warmup_due_sessions() -> bool:
    queue = get_queue(WARMUP_QUEUE_NAME)
    try:
        queue.enqueue_call(func=run_warmup_due_sessions, job_id="warmup-due-sessions", unique=True)
    except RedisError:
        _log_enqueue_failure(queue.name, "warmup-due-sessions", "RedisError")
        return False
    return True


def enqueue_warmup_dispatch_tick() -> bool:
    """Phase 1: enqueue a shadow-execution dispatch tick.

    Uses a fixed `job_id` plus `unique=True` so back-to-back ticks coalesce
    in Redis. Failure short-circuits to False so the async ticker can log
    the issue without raising.
    """
    queue = get_queue(WARMUP_DISPATCH_QUEUE_NAME)
    try:
        queue.enqueue_call(
            func=run_warmup_dispatch_tick,
            job_id="warmup-dispatch-tick",
            unique=True,
        )
    except RedisError:
        _log_enqueue_failure(queue.name, "warmup-dispatch-tick", "RedisError")
        return False
    return True


def enqueue_batch_start_auth(item_id: str, attempt_count: int, *, delay_seconds: int = 0) -> bool:
    queue = get_auth_queue()
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
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_telegram_auth_action(auth_session_id: str, workspace_id: str, action: str) -> bool:
    queue = get_auth_queue()
    job_id = f"telegram-auth-{auth_session_id}-{action}"
    try:
        queue.enqueue_call(
            func=run_telegram_auth_job,
            args=(auth_session_id, workspace_id, action),
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def _log_enqueue_failure(queue_name: str, job_id: str, error_class: str) -> None:
    log_warn(
        "queue_enqueue_failed",
        queue_name=queue_name,
        job_id=job_id,
        error_class=error_class,
    )


def remove_job_from_queue(job_id: str) -> bool:
    try:
        for queue in (get_profile_queue(), get_auth_queue()):
            queue.remove(job_id)
            for registry_cls in (DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry):
                registry = registry_cls(queue.name, connection=queue.connection)
                if job_id in registry.get_job_ids():
                    registry.remove(job_id, delete_job=True)
            try:
                Job.fetch(job_id, connection=queue.connection).delete()
            except NoSuchJobError:
                pass
    except RedisError:
        return False
    return True
