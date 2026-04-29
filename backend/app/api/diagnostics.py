from fastapi import APIRouter
from redis import Redis
from redis.exceptions import RedisError
from rq import Worker

from app.config import settings
from app.job_queue.rq import QUEUE_NAME
from app.schemas import DiagnosticsRead, LivePreflightRead
from app.services.live_preflight import LivePreflightService
from app.services.runtime_diagnostics import build_runtime_diagnostics

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/runtime", response_model=DiagnosticsRead)
def runtime_diagnostics():
    return DiagnosticsRead(**build_runtime_diagnostics())


@router.get("/live-preflight", response_model=LivePreflightRead)
def live_preflight():
    redis = Redis.from_url(settings.redis_url)
    service = LivePreflightService(
        database_url=settings.database_url,
        redis_ping=redis.ping,
        tdjson_path=settings.tdlib_shared_library_path,
        tdlib_api_id=settings.tdlib_api_id,
        tdlib_api_hash=settings.tdlib_api_hash,
        tdlib_database_root=settings.tdlib_database_root,
        tdlib_files_root=settings.tdlib_files_root,
        worker_expected=True,
        worker_status=lambda: _rq_worker_status(redis),
    )
    return LivePreflightRead(**service.run())


def _rq_worker_status(redis: Redis) -> str:
    try:
        workers = Worker.all(connection=redis)
    except RedisError:
        return "unknown"
    for worker in workers:
        if QUEUE_NAME in worker.queue_names():
            return "ready"
    return "missing"
