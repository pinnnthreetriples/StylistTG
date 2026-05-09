from __future__ import annotations

import argparse
from pathlib import PurePosixPath
from urllib.parse import urlparse

from app.scripts.common import (
    CheckReport,
    add_common_json_arg,
    bool_env,
    env_value,
    int_env,
    is_cloud_env,
    looks_production,
    main_guard,
    print_and_exit,
    sanitized_url,
    url_host,
)


def validate_cloud_config(env: dict[str, str] | None = None) -> CheckReport:
    report = CheckReport("cloud_config_check")
    app_env = env_value("APP_ENV", env) or "local"
    auth_mode = env_value("AUTH_MODE", env) or "local"
    db_mode = env_value("DB_CONNECTION_MODE", env) or "local"
    allow_local = bool_env("ALLOW_LOCAL_AUTH_IN_PROD", env)
    enforce_localhost = bool_env("ENFORCE_LOCALHOST_ONLY", env, default=True)
    api_stale_reaper = bool_env("STALE_JOB_REAPER_ENABLED", env, default=True)
    cors_origins = [origin.strip() for origin in (env_value("CORS_ORIGINS", env) or "").split(",") if origin.strip()]
    operator_token = env_value("OPERATOR_API_TOKEN", env)

    if app_env not in {"staging", "production"}:
        report.add("app_env", "WARN", "Cloud contour usually uses APP_ENV=staging or production", app_env=app_env)
    else:
        report.add("app_env", "PASS", "Cloud app env selected", app_env=app_env)

    if is_cloud_env(env) and auth_mode == "local" and not allow_local:
        report.add("auth_mode", "FAIL", "AUTH_MODE=local is not allowed for cloud mode", auth_mode=auth_mode)
    elif auth_mode != "supabase_jwt":
        report.add("auth_mode", "WARN", "Cloud contour should use AUTH_MODE=supabase_jwt", auth_mode=auth_mode)
    else:
        report.add("auth_mode", "PASS", "Supabase JWT auth mode selected")

    if is_cloud_env(env) and enforce_localhost:
        report.add("operator_guard", "FAIL", "Cloud API must set ENFORCE_LOCALHOST_ONLY=false")
    else:
        report.add("operator_guard", "PASS", "Operator localhost guard is compatible with this contour")
    if is_cloud_env(env) and not operator_token:
        report.add("operator_api_token", "FAIL", "Cloud API requires OPERATOR_API_TOKEN")
    elif operator_token:
        report.add("operator_api_token", "PASS", "Operator API token is configured")
    else:
        report.add("operator_api_token", "WARN", "Operator API token is not configured")

    if is_cloud_env(env) and (not cors_origins or "*" in cors_origins):
        report.add("cors_origins", "FAIL", "Cloud API requires explicit non-wildcard CORS_ORIGINS")
    elif cors_origins:
        report.add("cors_origins", "PASS", "CORS origins are explicit", count=len(cors_origins))
    else:
        report.add("cors_origins", "WARN", "CORS origins are empty")

    if is_cloud_env(env) and api_stale_reaper:
        report.add("api_stale_job_reaper", "FAIL", "Cloud API must set STALE_JOB_REAPER_ENABLED=false")
    else:
        report.add("api_stale_job_reaper", "PASS", "API stale job reaper is compatible with this contour")

    _required(report, "SUPABASE_AUTH_JWKS_URL", env)
    _required(report, "SUPABASE_AUTH_ISSUER", env)

    runtime_url = env_value("DATABASE_RUNTIME_URL", env) or env_value("DATABASE_URL", env)
    direct_url = env_value("DATABASE_DIRECT_URL", env)
    if not runtime_url:
        report.add("database_runtime_url", "FAIL", "DATABASE_RUNTIME_URL or DATABASE_URL is required")
    else:
        host = url_host(runtime_url)
        if db_mode == "neon" and "-pooler" not in host:
            report.add("database_runtime_url", "WARN", "Neon runtime URL usually uses pooled host", url=sanitized_url(runtime_url))
        else:
            report.add("database_runtime_url", "PASS", "Runtime database URL present", url=sanitized_url(runtime_url))
    if not direct_url:
        report.add("database_direct_url", "FAIL", "DATABASE_DIRECT_URL is required for migrations")
    else:
        host = url_host(direct_url)
        if "-pooler" in host:
            report.add("database_direct_url", "FAIL", "DATABASE_DIRECT_URL must not use Neon pooler host", url=sanitized_url(direct_url))
        else:
            report.add("database_direct_url", "PASS", "Direct migration database URL present", url=sanitized_url(direct_url))
    if runtime_url and direct_url and runtime_url == direct_url and not bool_env("ALLOW_IDENTICAL_DATABASE_URLS", env):
        report.add("database_url_split", "FAIL", "Runtime and direct DB URLs must be separate unless explicitly allowed")

    if db_mode != "neon":
        report.add("db_connection_mode", "WARN", "Cloud contour should use DB_CONNECTION_MODE=neon", db_connection_mode=db_mode)

    storage_backend = env_value("STORAGE_BACKEND", env) or "local"
    if storage_backend != "s3":
        report.add("storage_backend", "FAIL", "Cloud object storage requires STORAGE_BACKEND=s3", storage_backend=storage_backend)
    else:
        report.add("storage_backend", "PASS", "S3-compatible storage selected")
    for name in (
        "STORAGE_S3_ENDPOINT_URL",
        "STORAGE_S3_BUCKET",
        "STORAGE_S3_REGION",
        "STORAGE_S3_ACCESS_KEY_ID",
        "STORAGE_S3_SECRET_ACCESS_KEY",
    ):
        _required(report, name, env)
    ttl = int_env("STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS", env, default=300)
    if ttl < 60 or ttl > 3600:
        report.add("signed_url_ttl", "FAIL", "Signed URL TTL must be between 60 and 3600 seconds", ttl=ttl)
    else:
        report.add("signed_url_ttl", "PASS", "Signed URL TTL is within safe bounds", ttl=ttl)
    bucket = env_value("STORAGE_S3_BUCKET", env)
    if looks_production(bucket) and app_env != "production":
        report.add("storage_bucket_name", "FAIL", "Production-looking bucket name is not allowed outside production", bucket=bucket)

    redis_url = env_value("REDIS_URL", env)
    if not redis_url:
        report.add("redis_url", "FAIL", "REDIS_URL is required")
    elif urlparse(redis_url).scheme != "rediss":
        report.add("redis_url", "WARN", "rediss:// is preferred for cloud Redis", url=sanitized_url(redis_url))
    else:
        report.add("redis_url", "PASS", "Cloud Redis URL present", url=sanitized_url(redis_url))

    tdlib_db_root = env_value("TDLIB_DATABASE_ROOT", env)
    tdlib_files_root = env_value("TDLIB_FILES_ROOT", env)
    _required(report, "TDLIB_DATABASE_ROOT", env)
    _required(report, "TDLIB_FILES_ROOT", env)
    _check_tdlib_root(report, tdlib_db_root, env)
    _check_tdlib_root(report, tdlib_files_root, env)
    adapter = env_value("PROFILE_EXECUTION_ADAPTER", env) or "mock"
    live_enabled = bool_env("TDLIB_LIVE_ENABLED", env)
    allow_live_smoke = bool_env("ALLOW_TDLIB_LIVE_SMOKE", env)
    if live_enabled and not allow_live_smoke:
        report.add("tdlib_live_enabled", "FAIL", "TDLib live mode must stay disabled for cloud smoke without explicit live approval")
    else:
        report.add("tdlib_live_enabled", "PASS", "TDLib live mode is safe for cloud smoke", live_enabled=live_enabled)
    if adapter == "tdlib" and not allow_live_smoke:
        report.add("tdlib_adapter", "FAIL", "TDLib live adapter selected; refuse cloud smoke without explicit live approval")
    else:
        report.add("tdlib_adapter", "PASS", "Profile execution adapter is safe for cloud smoke", adapter=adapter)
    return report


def _required(report: CheckReport, name: str, env: dict[str, str] | None) -> None:
    if env_value(name, env):
        report.add(name.lower(), "PASS", f"{name} is present")
    else:
        report.add(name.lower(), "FAIL", f"{name} is required")


def _check_tdlib_root(report: CheckReport, tdlib_root: str | None, env: dict[str, str] | None) -> None:
    if not tdlib_root:
        return
    asset_root = env_value("STORAGE_LOCAL_ROOT", env) or env_value("LOCAL_STORAGE_PATH", env) or "storage"
    tdlib_path = PurePosixPath(tdlib_root.replace("\\", "/"))
    asset_path = PurePosixPath(asset_root.replace("\\", "/"))
    if tdlib_path == asset_path or asset_path in tdlib_path.parents:
        report.add("tdlib_storage_boundary", "FAIL", "TDLib root must not live under public asset storage", tdlib_root=tdlib_root)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate StylistTG cloud dev/staging environment.")
    add_common_json_arg(parser)
    args = parser.parse_args()
    print_and_exit(validate_cloud_config(), json_output=args.json)


if __name__ == "__main__":
    main_guard(main)

