from __future__ import annotations

from dataclasses import dataclass

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

PRODUCTION_QUEUE_NAMES = (
    AUTH_QUEUE_NAME,
    PROFILE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    STORY_QUEUE_NAME,
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    SCHEDULER_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
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
    ]


def worker_diagnostics(config: Settings = settings) -> dict:
    tdlib_live_enabled = bool(config.tdlib_live_enabled)
    runtime = detect_tdlib_runtime(config)
    session_root_configured = bool(config.tdlib_database_root and config.tdlib_files_root)
    return {
        "queues": [descriptor.to_dict() for descriptor in queue_descriptors()],
        "mode": "redis_rq",
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


def assert_queue_allowed(queue_name: str) -> None:
    if queue_name not in PRODUCTION_QUEUE_NAMES:
        raise ValueError(f"unsupported worker queue: {queue_name}")
