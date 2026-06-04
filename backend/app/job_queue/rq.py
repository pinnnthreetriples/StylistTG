from __future__ import annotations

from typing import Any, cast
from datetime import timedelta

from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry

from app.logging_utils import log_warn
from app.modules.account_onboarding.jobs import run_onboarding_item
from app.services.redis_client import redis_from_url
from app.workers.auth_batch_jobs import run_batch_start_auth
from app.workers.telegram_auth_jobs import run_telegram_auth_job
from app.workers.profile_jobs import run_profile_job
from app.services.worker_plane import (
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    AUTH_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    NEURO_COMMENT_QUEUE_NAME,
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
    "NEURO_COMMENT_QUEUE_NAME",
    "PROFILE_QUEUE_NAME",
    "QUEUE_NAME",
    "SCHEDULER_QUEUE_NAME",
    "STORY_QUEUE_NAME",
    "WARMUP_DISPATCH_QUEUE_NAME",
    "WARMUP_QUEUE_NAME",
    "enqueue_account_update_job",
    "enqueue_account_onboarding_item",
    "enqueue_batch_start_auth",
    "enqueue_telegram_auth_action",
    "enqueue_profile_job",
    "enqueue_neuro_generate_comment",
    "enqueue_neuro_observe_campaign",
    "enqueue_neuro_refresh_target_metadata",
    "enqueue_neuro_observe_target",
    "enqueue_neuro_send_attempt",
    "neuro_generate_comment_job_id",
    "enqueue_warmup_due_sessions",
    "enqueue_warmup_dispatch_tick",
    "get_auth_queue",
    "get_profile_queue",
    "get_queue",
    "is_job_in_redis",
    "reenqueue_job_with_delay",
    "remove_job_from_queue",
]


def get_profile_queue() -> Queue:
    connection = redis_from_url()
    return Queue(PROFILE_QUEUE_NAME, connection=connection)


def get_auth_queue() -> Queue:
    connection = redis_from_url()
    return Queue(AUTH_QUEUE_NAME, connection=connection)


def get_queue(queue_name: str) -> Queue:
    if queue_name not in PRODUCTION_QUEUE_NAMES:
        raise ValueError(f"unsupported queue: {queue_name}")
    connection = redis_from_url()
    return Queue(queue_name, connection=connection)


def enqueue_profile_job(job_id: str) -> bool:
    queue = get_profile_queue()
    try:
        cast(Any, queue).enqueue_call(
            func=run_profile_job, args=(job_id,), job_id=job_id, unique=True
        )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_account_update_job(job_id: str) -> bool:
    from app.modules.account_editing.enqueue import (
        enqueue_account_update_job as module_enqueue_account_update_job,
    )

    return module_enqueue_account_update_job(job_id)


def enqueue_warmup_due_sessions() -> bool:
    from app.modules.warmup.enqueue import (
        enqueue_warmup_due_sessions as module_enqueue_warmup_due_sessions,
    )

    return module_enqueue_warmup_due_sessions()


def enqueue_warmup_dispatch_tick() -> bool:
    from app.modules.warmup.enqueue import (
        enqueue_warmup_dispatch_tick as module_enqueue_warmup_dispatch_tick,
    )

    return module_enqueue_warmup_dispatch_tick()


def enqueue_batch_start_auth(item_id: str, attempt_count: int, *, delay_seconds: int = 0) -> bool:
    queue = get_auth_queue()
    job_id = f"auth-start-{item_id}-attempt-{attempt_count}"
    try:
        if delay_seconds > 0:
            cast(Any, queue).enqueue_in(
                timedelta(seconds=delay_seconds),
                run_batch_start_auth,
                args=(item_id,),
                job_id=job_id,
            )
        else:
            cast(Any, queue).enqueue_call(
                func=run_batch_start_auth, args=(item_id,), job_id=job_id, unique=True
            )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_account_onboarding_item(
    item_id: str, retry_count: int, *, delay_seconds: int = 0
) -> bool:
    queue = get_auth_queue()
    job_id = f"account-onboarding-{item_id}-retry-{retry_count}"
    try:
        if delay_seconds > 0:
            cast(Any, queue).enqueue_in(
                timedelta(seconds=delay_seconds),
                run_onboarding_item,
                args=(item_id,),
                job_id=job_id,
            )
        else:
            cast(Any, queue).enqueue_call(
                func=run_onboarding_item,
                args=(item_id,),
                job_id=job_id,
                unique=True,
            )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_telegram_auth_action(auth_session_id: str, workspace_id: str, action: str) -> bool:
    queue = get_auth_queue()
    job_id = f"telegram-auth-{auth_session_id}-{action}"
    try:
        cast(Any, queue).enqueue_call(
            func=run_telegram_auth_job,
            args=(auth_session_id, workspace_id, action),
            job_id=job_id,
            unique=True,
        )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def enqueue_neuro_observe_campaign(
    campaign_id: str, workspace_id: str, *, limit: int | None, generate: bool
) -> bool:
    from app.modules.neuro_commenting.enqueue import (
        enqueue_neuro_observe_campaign as module_enqueue_neuro_observe_campaign,
    )

    return module_enqueue_neuro_observe_campaign(
        campaign_id, workspace_id, limit=limit, generate=generate
    )


def enqueue_neuro_observe_target(
    campaign_id: str, target_id: str, workspace_id: str, *, limit: int | None, generate: bool
) -> bool:
    from app.modules.neuro_commenting.enqueue import (
        enqueue_neuro_observe_target as module_enqueue_neuro_observe_target,
    )

    return module_enqueue_neuro_observe_target(
        campaign_id, target_id, workspace_id, limit=limit, generate=generate
    )


def enqueue_neuro_generate_comment(
    campaign_id: str,
    workspace_id: str,
    observed_post_id: str,
    *,
    force: bool = False,
    job_id: str | None = None,
) -> bool:
    from app.modules.neuro_commenting.enqueue import (
        enqueue_neuro_generate_comment as module_enqueue_neuro_generate_comment,
    )

    return module_enqueue_neuro_generate_comment(
        campaign_id,
        workspace_id,
        observed_post_id,
        force=force,
        job_id=job_id,
    )


def enqueue_neuro_refresh_target_metadata(
    campaign_id: str, target_id: str, workspace_id: str
) -> bool:
    from app.modules.neuro_commenting.enqueue import (
        enqueue_neuro_refresh_target_metadata as module_enqueue_neuro_refresh_target_metadata,
    )

    return module_enqueue_neuro_refresh_target_metadata(campaign_id, target_id, workspace_id)


def enqueue_neuro_send_attempt(attempt_id: str, workspace_id: str) -> bool:
    from app.modules.neuro_commenting.enqueue import (
        enqueue_neuro_send_attempt as module_enqueue_neuro_send_attempt,
    )

    return module_enqueue_neuro_send_attempt(attempt_id, workspace_id)


def neuro_generate_comment_job_id(observed_post_id: str, *, force: bool = False) -> str:
    from app.modules.neuro_commenting.enqueue import (
        neuro_generate_comment_job_id as module_neuro_generate_comment_job_id,
    )

    return module_neuro_generate_comment_job_id(observed_post_id, force=force)


def reenqueue_job_with_delay(
    job_id: str, *, delay_seconds: int, workflow_type: str | None = None
) -> bool:
    if workflow_type == "account_update":
        from app.modules.account_editing.enqueue import (
            reenqueue_account_update_job_with_delay as module_reenqueue_account_update_job,
        )

        return module_reenqueue_account_update_job(job_id, delay_seconds=delay_seconds)

    queue = get_profile_queue()
    func = run_profile_job
    retry_job_id = f"retry-{job_id}"
    try:
        _cancel_existing_job(queue, retry_job_id)
        cast(Any, queue).enqueue_in(
            timedelta(seconds=delay_seconds), func, job_id, job_id=retry_job_id
        )
    except RedisError:
        _log_enqueue_failure(queue.name, job_id, "RedisError")
        return False
    return True


def is_job_in_redis(job_id: str) -> bool:
    """Check if a DB job is present in any active Redis state (queued/deferred/started)."""
    queue = get_profile_queue()
    active_statuses = {"queued", "deferred", "started", "scheduled"}
    for check_id in (job_id, f"retry-{job_id}"):
        try:
            rq_job = cast(Any, Job).fetch(check_id, connection=queue.connection)
            status = rq_job.get_status()
            if status in active_statuses:
                return True
        except NoSuchJobError:
            continue
    return False


def _cancel_existing_job(queue: Queue, rq_job_id: str) -> None:
    try:
        existing = cast(Any, Job).fetch(rq_job_id, connection=queue.connection)
        existing.delete()
    except NoSuchJobError:
        # Cancellation is idempotent: a missing job means already cancelled/expired.
        return


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
                cast(Any, Job).fetch(job_id, connection=queue.connection).delete()
            except NoSuchJobError:
                # Already removed via queue.remove or registry.remove above.
                continue
    except RedisError:
        return False
    return True
