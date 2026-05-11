from fastapi import APIRouter, Depends
from redis import Redis
from redis.exceptions import RedisError
from rq import Worker
from typing import Any, cast

from app.config import settings
from app.job_queue.rq import AUTH_QUEUE_NAME, PROFILE_QUEUE_NAME
from app.schemas import DiagnosticsRead, FrontendDiagnosticsSummaryRead, LivePreflightRead
from app.services.auth_context import AuthContext, require_authenticated, require_role
from app.services.frontend_diagnostics import build_frontend_diagnostics_summary
from app.services.live_preflight import LivePreflightService
from app.services.runtime_diagnostics import build_runtime_diagnostics

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/frontend-summary", response_model=FrontendDiagnosticsSummaryRead)
def frontend_summary(
    _auth: AuthContext = Depends(require_authenticated),
):
    return build_frontend_diagnostics_summary(build_runtime_diagnostics())


@router.get("/runtime", response_model=DiagnosticsRead)
def runtime_diagnostics(_auth: AuthContext = Depends(require_role("admin"))):
    diagnostics = build_runtime_diagnostics()
    return DiagnosticsRead(
        database=str(diagnostics["database"]),
        redis=str(diagnostics["redis"]),
        tdlib=str(diagnostics["tdlib"]),
    )


@router.get("/live-preflight", response_model=LivePreflightRead)
def live_preflight(_auth: AuthContext = Depends(require_role("admin"))):
    redis = cast(Redis, cast(Any, Redis).from_url(settings.redis_url))

    def redis_ping() -> bool:
        return bool(cast(Any, redis).ping())

    service = LivePreflightService(
        database_url=settings.database_url,
        redis_ping=redis_ping,
        tdjson_path=settings.tdlib_shared_library_path,
        tdlib_api_id=settings.tdlib_api_id,
        tdlib_api_hash=settings.tdlib_api_hash,
        tdlib_database_root=settings.tdlib_database_root,
        tdlib_files_root=settings.tdlib_files_root,
        worker_expected=True,
        profile_worker_status=lambda: _rq_queue_worker_status(redis, PROFILE_QUEUE_NAME),
        auth_worker_status=lambda: _rq_queue_worker_status(redis, AUTH_QUEUE_NAME),
    )
    result = service.run()
    return LivePreflightRead(
        tdjson_present=bool(result["tdjson_present"]),
        tdlib_credentials_present=bool(result["tdlib_credentials_present"]),
        postgres_reachable=bool(result["postgres_reachable"]),
        redis_reachable=bool(result["redis_reachable"]),
        storage_writable=bool(result["storage_writable"]),
        rq_worker_expected=bool(result["rq_worker_expected"]),
        rq_worker_status=result["rq_worker_status"]
        if isinstance(result["rq_worker_status"], str)
        else None,
        profile_worker_status=result["profile_worker_status"]
        if isinstance(result["profile_worker_status"], str)
        else None,
        auth_worker_status=result["auth_worker_status"]
        if isinstance(result["auth_worker_status"], str)
        else None,
        overall_status=str(result["overall_status"]),
    )


def _rq_queue_worker_status(redis: Redis, queue_name: str) -> str:
    try:
        workers = cast(list[Any], cast(Any, Worker).all(connection=redis))
    except RedisError:
        return "unknown"
    for worker in workers:
        if queue_name in worker.queue_names():
            return "ready"
    return "missing"
