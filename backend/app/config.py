from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://stylisttg:stylisttg@localhost:5432/stylisttg"
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
    profile_photo_max_bytes: int = 20 * 1024 * 1024
    profile_audio_max_bytes: int = 20 * 1024 * 1024
    story_image_max_bytes: int = 10 * 1024 * 1024
    story_video_max_bytes: int = 50 * 1024 * 1024
    stories_enabled: bool = True
    stories_tdlib_live_enabled: bool = False
    ffprobe_path: str | None = None
    ffmpeg_path: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
