from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings, settings
from app.services.tdlib_runtime import detect_tdlib_runtime
from app.services.worker_plane import PRODUCTION_QUEUE_NAMES


def build_frontend_diagnostics_summary(
    runtime: dict[str, str],
    *,
    config: Settings = settings,
) -> dict:
    storage_backend = config.storage_backend
    bucket_configured = bool(config.storage_s3_bucket) if storage_backend == "s3" else bool(config.storage_root)
    signed_url_enabled = storage_backend == "s3"
    public_base_url_configured = bool(config.storage_public_base_url or config.storage_s3_public_base_url)
    profile_adapter = config.profile_execution_adapter
    tdlib_runtime = detect_tdlib_runtime(config)
    live_enabled = bool(config.tdlib_live_enabled) and profile_adapter == "tdlib"
    session_root_configured = bool(config.tdlib_database_root and config.tdlib_files_root)
    return {
        "app_env": config.app_env,
        "auth_mode": config.auth_mode,
        "db": {
            "status": runtime.get("database", "unknown"),
            "mode": config.db_connection_mode,
        },
        "redis": {
            "status": runtime.get("redis", "unknown"),
            "configured": bool(config.redis_url),
        },
        "storage": {
            "backend": storage_backend,
            "bucket_configured": bucket_configured,
            "signed_url_enabled": signed_url_enabled,
            "public_base_url_configured": public_base_url_configured,
        },
        "tdlib": {
            "status": runtime.get("tdlib", "unknown"),
            "profile_execution_adapter": profile_adapter,
            "live_enabled": live_enabled,
            "runtime_mode": tdlib_runtime.runtime_mode,
            "library_configured": tdlib_runtime.library_configured,
            "library_loadable": tdlib_runtime.library_loadable,
            "api_id_configured": tdlib_runtime.api_id_configured,
            "api_hash_configured": tdlib_runtime.api_hash_configured,
            "auth_worker_ready": True,
            "readonly_smoke_available": tdlib_runtime.readonly_smoke_available,
            "session_root_configured": session_root_configured,
            "execution_plane_ready": live_enabled and tdlib_runtime.configured and session_root_configured,
            "error_code": tdlib_runtime.error_code,
        },
        "workers": {
            "queues": list(PRODUCTION_QUEUE_NAMES),
            "mode": "redis_rq",
            "scheduler_enabled": config.scheduler_enabled,
            "reaper_mode": config.reaper_mode,
        },
        "generated_at": datetime.now(UTC),
    }
