from __future__ import annotations

import importlib
from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast

from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.job_queue.rq import get_queue
from app.logging_utils import log_warn
from app.modules.contracts import WorkflowArgsMode
from app.modules.registry import get_workflow_spec


def resolve_handler(handler_path: str) -> Callable[..., Any]:
    module_name, function_name = handler_path.split(":", 1)
    module = importlib.import_module(module_name)
    handler = getattr(module, function_name)
    return cast(Callable[..., Any], handler)


def enqueue_workflow(
    *,
    workflow_type: str,
    job_id: str,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    unique: bool = True,
) -> bool:
    spec = get_workflow_spec(workflow_type)
    queue = get_queue(spec.queue_name)
    handler = resolve_handler(spec.handler_path)

    resolved_args = args if args is not None else _default_args(spec.args_mode, job_id)

    try:
        cast(Any, queue).enqueue_call(
            func=handler,
            args=resolved_args,
            kwargs=kwargs or {},
            job_id=job_id,
            unique=unique,
        )
    except RedisError:
        log_warn(
            "workflow_enqueue_failed",
            workflow_type=workflow_type,
            queue_name=spec.queue_name,
            job_id=job_id,
            error_class="RedisError",
        )
        return False

    return True


def reenqueue_workflow_with_delay(
    *,
    workflow_type: str,
    job_id: str,
    delay_seconds: int,
) -> bool:
    spec = get_workflow_spec(workflow_type)
    queue = get_queue(spec.queue_name)
    handler = resolve_handler(spec.handler_path)
    retry_job_id = f"retry-{job_id}"
    try:
        _cancel_existing_job(queue, retry_job_id)
        cast(Any, queue).enqueue_in(
            timedelta(seconds=delay_seconds), handler, job_id, job_id=retry_job_id
        )
    except RedisError:
        log_warn(
            "workflow_reenqueue_failed",
            workflow_type=workflow_type,
            queue_name=spec.queue_name,
            job_id=job_id,
            error_class="RedisError",
        )
        return False
    return True


def _default_args(args_mode: WorkflowArgsMode, job_id: str) -> tuple[Any, ...]:
    if args_mode == WorkflowArgsMode.JOB_ID:
        return (job_id,)
    if args_mode == WorkflowArgsMode.CUSTOM:
        raise ValueError("custom workflow args must be provided")
    return ()


def _cancel_existing_job(queue: Any, rq_job_id: str) -> None:
    try:
        existing = cast(Any, Job).fetch(rq_job_id, connection=queue.connection)
        existing.delete()
    except NoSuchJobError:
        pass
