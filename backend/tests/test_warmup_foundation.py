from app.config import Settings
from app.models import WarmupEvent, WarmupSession, WarmupStatus, WarmupStrategy, WarmupTaskRun


def test_warmup_models_match_foundation_tables() -> None:
    assert WarmupStrategy.__tablename__ == "warmup_strategy"
    assert WarmupSession.__tablename__ == "warmup_session"
    assert WarmupEvent.__tablename__ == "warmup_event"
    assert WarmupTaskRun.__tablename__ == "warmup_task_run"
    assert WarmupStatus.SCHEDULED == "scheduled"


def test_warmup_settings_default_to_safe_dry_run() -> None:
    settings = Settings()

    assert settings.warmup_workers_enabled is False
    assert settings.warmup_dry_run is True
    assert settings.warmup_default_cadence_hours == 24
    assert settings.warmup_max_consecutive_failures == 3


def test_warmup_router_uses_expected_prefix() -> None:
    from app.api.warmup import router

    assert router.prefix == "/api/warmup"
