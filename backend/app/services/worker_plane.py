from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry

from app.config import Settings, settings
from app.services.tdlib_runtime import detect_tdlib_runtime

AUTH_QUEUE_NAME = "auth_jobs"
PROFILE_QUEUE_NAME = "profile_jobs"
MEDIA_QUEUE_NAME = "media_jobs"
STORY_QUEUE_NAME = "story_jobs"
ACCOUNT_LIFECYCLE_QUEUE_NAME = "account_lifecycle_jobs"
MAINTENANCE_QUEUE_NAME = "maintenance_jobs"
SCHEDULER_QUEUE_NAME = "scheduler_jobs"
WARMUP_QUEUE_NAME = "warmup_jobs"
WARMUP_DISPATCH_QUEUE_NAME = "warmup_dispatch_jobs"

PRODUCTION_QUEUE_NAMES = (
    AUTH_QUEUE_NAME,
    PROFILE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    STORY_QUEUE_NAME,
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    SCHEDULER_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
)


@dataclass(frozen=True)
class QueueDescriptor:
    name: str
    purpose: str
    live_execution_default: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "live_execution_default": self.live_execution_default,
        }


def queue_descriptors() -> list[QueueDescriptor]:
    return [
        QueueDescriptor(AUTH_QUEUE_NAME, "Telegram auth, login, and reauth jobs"),
        QueueDescriptor(PROFILE_QUEUE_NAME, "Profile text, photo, and profile update jobs"),
        QueueDescriptor(MEDIA_QUEUE_NAME, "Media upload and normalization jobs"),
        QueueDescriptor(STORY_QUEUE_NAME, "Story preparation and future story execution jobs"),
        QueueDescriptor(ACCOUNT_LIFECYCLE_QUEUE_NAME, "Account deletion/export/lifecycle jobs"),
        QueueDescriptor(MAINTENANCE_QUEUE_NAME, "Dry-run maintenance and safe cleanup reports"),
        QueueDescriptor(SCHEDULER_QUEUE_NAME, "Future scheduled checks and enqueue decisions"),
        QueueDescriptor(WARMUP_QUEUE_NAME, "Dry-run account preparation jobs"),
        QueueDescriptor(
            WARMUP_DISPATCH_QUEUE_NAME,
            "Live warmup micro-session dispatch (network + advanced execution modes)",
            live_execution_default=True,
        ),
    ]


def worker_diagnostics(config: Settings = settings) -> dict:
    tdlib_live_enabled = bool(config.tdlib_live_enabled)
    runtime = detect_tdlib_runtime(config)
    session_root_configured = bool(config.tdlib_database_root and config.tdlib_files_root)
    return {
        "queues": [descriptor.to_dict() for descriptor in queue_descriptors()],
        "mode": "redis_rq",
        "redis": _redis_queue_snapshot(config),
        "scheduler": {
            "enabled": config.scheduler_enabled,
            "mode": "safe_enqueue" if config.scheduler_enabled else "off",
        },
        "reaper": {
            "enabled": config.reaper_enabled,
            "mode": config.reaper_mode,
            "destructive_by_default": False,
        },
        "rate_limits": {
            "auth_jobs_per_tenant_per_hour": config.rate_limit_auth_jobs_per_tenant_per_hour,
            "profile_jobs_per_tenant_per_hour": config.rate_limit_profile_jobs_per_tenant_per_hour,
            "media_jobs_per_tenant_per_hour": config.rate_limit_media_jobs_per_tenant_per_hour,
            "story_jobs_per_tenant_per_hour": config.rate_limit_story_jobs_per_tenant_per_hour,
            "account_jobs_per_hour": config.rate_limit_account_jobs_per_hour,
        },
        "tdlib": {
            "live_enabled": tdlib_live_enabled,
            "adapter": config.profile_execution_adapter,
            "runtime_mode": runtime.runtime_mode,
            "library_configured": runtime.library_configured,
            "library_loadable": runtime.library_loadable,
            "api_id_configured": runtime.api_id_configured,
            "api_hash_configured": runtime.api_hash_configured,
            "readonly_smoke_available": runtime.readonly_smoke_available,
            "auth_worker_ready": True,
            "session_root_configured": session_root_configured,
            "execution_plane_ready": tdlib_live_enabled
            and config.profile_execution_adapter == "tdlib"
            and runtime.configured
            and session_root_configured,
            "error_code": runtime.error_code,
        },
    }


def _redis_queue_snapshot(config: Settings) -> dict[str, Any]:
    queue_names = [descriptor.name for descriptor in queue_descriptors()]
    try:
        connection = Redis.from_url(
            config.redis_url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        connection.ping()
        workers = Worker.all(connection=connection)
        return {
            "status": "ok",
            "worker_count": len(workers),
            "queues": [_queue_snapshot(connection, queue_name) for queue_name in queue_names],
        }
    except (RedisError, ValueError) as exc:
        return {
            "status": "down",
            "worker_count": 0,
            "queues": [
                {
                    "name": queue_name,
                    "depth": None,
                    "failed": None,
                    "started": None,
                    "deferred": None,
                    "oldest_job_age_seconds": None,
                }
                for queue_name in queue_names
            ],
            "error_class": exc.__class__.__name__,
        }


def _queue_snapshot(connection: Redis, queue_name: str) -> dict[str, Any]:
    try:
        queue = Queue(queue_name, connection=connection)
        return {
            "name": queue_name,
            "depth": queue.count,
            "failed": len(FailedJobRegistry(queue_name, connection=connection)),
            "started": len(StartedJobRegistry(queue_name, connection=connection)),
            "deferred": len(DeferredJobRegistry(queue_name, connection=connection)),
            "oldest_job_age_seconds": _oldest_job_age_seconds(queue, connection),
        }
    except RedisError as exc:
        return {
            "name": queue_name,
            "depth": None,
            "failed": None,
            "started": None,
            "deferred": None,
            "oldest_job_age_seconds": None,
            "error_class": exc.__class__.__name__,
        }


def _oldest_job_age_seconds(queue: Queue, connection: Redis) -> int | None:
    job_ids = queue.get_job_ids(offset=0, length=1)
    if not job_ids:
        return None
    try:
        job = Job.fetch(job_ids[0], connection=connection)
    except NoSuchJobError:
        return None
    if job.enqueued_at is None:
        return None
    enqueued_at = job.enqueued_at
    if enqueued_at.tzinfo is None:
        enqueued_at = enqueued_at.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - enqueued_at).total_seconds()))


def assert_queue_allowed(queue_name: str) -> None:
    if queue_name not in PRODUCTION_QUEUE_NAMES:
        raise ValueError(f"unsupported worker queue: {queue_name}")
