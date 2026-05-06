from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://stylisttg:stylisttg@localhost:5432/stylisttg"
    database_runtime_url: str | None = None
    database_direct_url: str | None = None
    db_connection_mode: str = "local"
    db_pool_pre_ping: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 10
    redis_url: str = "redis://127.0.0.1:6379/0"
    local_storage_path: Path = Path("storage")
    storage_backend: str = "local"
    storage_local_root: Path | None = None
    storage_public_base_url: str | None = None
    storage_s3_endpoint_url: str | None = None
    storage_s3_bucket: str | None = None
    storage_s3_region: str | None = None
    storage_s3_access_key_id: str | None = None
    storage_s3_secret_access_key: SecretStr | None = None
    storage_s3_force_path_style: bool = True
    storage_s3_signed_url_expires_seconds: int = 300
    storage_s3_public_base_url: str | None = None
    tdlib_storage_backend: str = "local"
    lock_stale_seconds: int = 60
    tdlib_api_id: int | None = None
    tdlib_api_hash: str | None = None
    tdlib_database_root: Path = Path("tdlib/database")
    tdlib_files_root: Path = Path("tdlib/files")
    tdlib_shared_library_path: Path | None = None
    tdlib_runtime_mode: str = "mock"
    tdlib_auth_job_timeout_seconds: int = 300
    tdlib_readonly_smoke_enabled: bool = False
    telegram_api_id: int | None = None
    telegram_api_hash: SecretStr | None = None
    account_import_max_file_count: int = 200
    account_import_max_uncompressed_bytes: int = 25 * 1024 * 1024
    account_import_max_depth: int = 8
    account_import_max_upload_bytes: int = 25 * 1024 * 1024
    tdlib_receive_timeout_seconds: float = 1.0
    tdlib_auth_timeout_seconds: float = 30.0
    profile_audio_upload_timeout_seconds: float = 20.0
    tdlib_proxy_apply_timeout_seconds: float = 10.0
    tdlib_use_test_dc: bool = False
    tdlib_production_auth_enabled: bool = True
    auth_start_cooldown_seconds: int = 120
    auth_daily_start_limit: int = 5
    profile_execution_adapter: str = "mock"
    profile_job_timeout_seconds: float = 120.0
    queue_inline_fallback_enabled: bool = False
    stale_job_timeout_seconds: int = 300
    stale_job_reaper_enabled: bool = True
    stale_job_reaper_interval_seconds: int = 60
    profile_job_cooldown_seconds: int = 120
    profile_update_cooldown_seconds: int = 300
    username_cooldown_seconds: int = 1800
    profile_photo_cooldown_seconds: int = 900
    profile_music_cooldown_seconds: int = 900
    story_post_cooldown_seconds: int = 3600
    story_delete_cooldown_seconds: int = 900
    unknown_capability_policy: str = "warning_only"
    recent_failure_policy: str = "warning_only"
    fresh_validity_required: str = "if_stale"
    fresh_validity_max_age_minutes: int = 30
    manual_hard_blocker_override_enabled: bool = False
    proxy_credentials_encryption_key: str | None = None
    operator_api_token: str | None = None
    enforce_localhost_only: bool = True
    operator_allowed_client_hosts: str = "127.0.0.1,::1,localhost,testclient"
    cors_origins: str = ""
    profile_photo_max_bytes: int = 20 * 1024 * 1024
    profile_audio_max_bytes: int = 20 * 1024 * 1024
    story_image_max_bytes: int = 10 * 1024 * 1024
    story_video_max_bytes: int = 50 * 1024 * 1024
    stories_enabled: bool = True
    stories_tdlib_live_enabled: bool = False
    tdlib_live_enabled: bool = False
    account_export_ttl_days: int = 7
    account_deletion_log_retention_days: int = 90
    account_deletion_allow_hard_delete: bool = False
    account_deletion_dry_run_default: bool = True
    scheduler_enabled: bool = False
    reaper_enabled: bool = False
    reaper_mode: str = "dry_run"
    rate_limit_auth_jobs_per_tenant_per_hour: int = 20
    rate_limit_profile_jobs_per_tenant_per_hour: int = 100
    rate_limit_media_jobs_per_tenant_per_hour: int = 50
    rate_limit_story_jobs_per_tenant_per_hour: int = 20
    rate_limit_account_jobs_per_hour: int = 10
    ffprobe_path: str | None = None
    ffmpeg_path: str | None = None
    auth_mode: str = "local"
    allow_local_auth_in_prod: bool = False
    supabase_auth_jwks_url: str | None = None
    supabase_auth_issuer: str | None = None
    supabase_auth_audience: str | None = None
    supabase_auth_jwks_cache_ttl_seconds: int = 600
    supabase_auth_jwks_refresh_on_kid_miss: bool = True
    supabase_auth_jwks_request_timeout_seconds: float = 5.0
    supabase_auth_jwks_max_retries: int = 1
    default_workspace_mode: str = "local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def runtime_database_url(self) -> str:
        return self.database_runtime_url or self.database_url

    @property
    def migration_database_url(self) -> str:
        return self.database_direct_url or self.database_url

    @property
    def storage_root(self) -> Path:
        return self.storage_local_root or self.local_storage_path

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        cloud_or_prod = self.app_env not in {"local", "development", "test"} or self.db_connection_mode == "neon"
        if cloud_or_prod and self.auth_mode == "local" and not self.allow_local_auth_in_prod:
            raise ValueError(
                "AUTH_MODE=local is not allowed in production/cloud mode. "
                "Use AUTH_MODE=supabase_jwt or explicitly set "
                "ALLOW_LOCAL_AUTH_IN_PROD=true for controlled non-production testing."
            )
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")
        if self.tdlib_storage_backend != "local":
            raise ValueError("TDLIB_STORAGE_BACKEND currently supports only local backend")
        if self.storage_backend == "s3":
            missing = [
                name
                for name, value in {
                    "STORAGE_S3_ENDPOINT_URL": self.storage_s3_endpoint_url,
                    "STORAGE_S3_BUCKET": self.storage_s3_bucket,
                    "STORAGE_S3_ACCESS_KEY_ID": self.storage_s3_access_key_id,
                    "STORAGE_S3_SECRET_ACCESS_KEY": self.storage_s3_secret_access_key,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"STORAGE_BACKEND=s3 requires {', '.join(missing)}")
        return self


settings = Settings()
