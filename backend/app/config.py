from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://stylisttg:stylisttg@localhost:5432/stylisttg"
    database_runtime_url: str | None = None
    database_direct_url: str | None = None
    db_connection_mode: str = "local"
    db_pool_pre_ping: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 10
    redis_url: str = "redis://127.0.0.1:6379/0"
    local_storage_path: Path = Path("storage")
    lock_stale_seconds: int = 60
    tdlib_api_id: int | None = None
    tdlib_api_hash: str | None = None
    tdlib_database_root: Path = Path("tdlib/database")
    tdlib_files_root: Path = Path("tdlib/files")
    tdlib_shared_library_path: Path | None = None
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
    profile_photo_max_bytes: int = 20 * 1024 * 1024
    profile_audio_max_bytes: int = 20 * 1024 * 1024
    story_image_max_bytes: int = 10 * 1024 * 1024
    story_video_max_bytes: int = 50 * 1024 * 1024
    stories_enabled: bool = True
    stories_tdlib_live_enabled: bool = False
    ffprobe_path: str | None = None
    ffmpeg_path: str | None = None
    auth_mode: str = "local"
    supabase_auth_jwks_url: str | None = None
    supabase_auth_issuer: str | None = None
    supabase_auth_audience: str | None = None
    default_workspace_mode: str = "local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def runtime_database_url(self) -> str:
        return self.database_runtime_url or self.database_url

    @property
    def migration_database_url(self) -> str:
        return self.database_direct_url or self.database_url


settings = Settings()
