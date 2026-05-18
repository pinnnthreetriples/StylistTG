from __future__ import annotations

from types import SimpleNamespace

from app.runtime.preflight import check_runtime_role
from app.services.worker_plane import (
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    PROFILE_QUEUE_NAME,
    STORY_QUEUE_NAME,
)


def test_unknown_role_returns_safe_error_without_runtime_access() -> None:
    result = check_runtime_role("unknown_role", config=_config())

    assert result.known is False
    assert result.errors == ("unknown runtime role: unknown_role",)
    assert result.allowed_queues == ()


def test_queue_violations_are_reported_without_redis_or_tdlib_access() -> None:
    result = check_runtime_role(
        "warmup_dispatch_worker",
        queues=(PROFILE_QUEUE_NAME,),
        config=_config(tdlib_live_enabled=True, session_roots=True),
    )

    assert result.known is True
    assert result.queue_violations == (PROFILE_QUEUE_NAME,)
    assert "queue not allowed for role warmup_dispatch_worker: profile_jobs" in result.errors


def test_tdlib_and_session_checks_are_config_only() -> None:
    result = check_runtime_role("auth_worker", config=_config())

    assert result.requires_tdlib is True
    assert result.requires_session_storage is True
    assert result.session_root_configured is False
    assert "tdlib session root is not configured" in result.errors


def test_reserved_role_preflight_reports_allowed_queues_without_live_requirements() -> None:
    expectations = {
        "maintenance_worker": (MAINTENANCE_QUEUE_NAME,),
        "media_worker": (MEDIA_QUEUE_NAME,),
        "story_worker": (STORY_QUEUE_NAME,),
        "account_lifecycle_worker": (ACCOUNT_LIFECYCLE_QUEUE_NAME,),
    }

    for role_name, queues in expectations.items():
        result = check_runtime_role(role_name, queues=queues, config=_config())

        assert result.known is True
        assert result.allowed_queues == queues
        assert result.queue_violations == ()
        assert result.requires_tdlib is False
        assert result.requires_session_storage is False
        assert result.allows_live_tdlib is False
        assert result.errors == ()


def test_reserved_role_preflight_rejects_cross_role_queue() -> None:
    result = check_runtime_role(
        "media_worker",
        queues=(STORY_QUEUE_NAME,),
        config=_config(),
    )

    assert result.known is True
    assert result.queue_violations == (STORY_QUEUE_NAME,)
    assert "queue not allowed for role media_worker: story_jobs" in result.errors


def _config(*, tdlib_live_enabled: bool = False, session_roots: bool = False):
    return SimpleNamespace(
        tdlib_database_root="db-root" if session_roots else None,
        tdlib_files_root="files-root" if session_roots else None,
        tdlib_live_enabled=tdlib_live_enabled,
    )
