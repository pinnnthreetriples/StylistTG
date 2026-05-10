from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import QueueDescriptorRead, RetryPolicyRead, WorkerDiagnosticsRead
from app.services.auth_context import AuthContext, require_authenticated, require_role
from app.services.retry_policy import retry_policy_for
from app.services.worker_plane import queue_descriptors, worker_diagnostics

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("/queues", response_model=list[QueueDescriptorRead])
def get_worker_queues(_auth: AuthContext = Depends(require_authenticated)):
    return [
        QueueDescriptorRead(
            name=descriptor.name,
            purpose=descriptor.purpose,
            live_execution_default=descriptor.live_execution_default,
        )
        for descriptor in queue_descriptors()
    ]


@router.get("/diagnostics", response_model=WorkerDiagnosticsRead)
def get_worker_diagnostics(_auth: AuthContext = Depends(require_role("admin"))):
    return WorkerDiagnosticsRead(**worker_diagnostics())


@router.get("/job-policies", response_model=dict[str, RetryPolicyRead])
def get_job_policies(_auth: AuthContext = Depends(require_authenticated)):
    return {
        category: RetryPolicyRead(
            retry=policy.retry,
            max_attempts=policy.max_attempts,
            interval_seconds=policy.interval_seconds,
            failure_ttl_seconds=policy.failure_ttl_seconds,
            result_ttl_seconds=policy.result_ttl_seconds,
            error_category=policy.error_category,
        )
        for category in (
            "flood_wait",
            "auth_required",
            "proxy_failed",
            "tdlib_unavailable",
            "validation_error",
            "unknown_transient",
        )
        for policy in (retry_policy_for(category),)
    }
