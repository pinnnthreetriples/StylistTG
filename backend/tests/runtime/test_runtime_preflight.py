from __future__ import annotations

from types import SimpleNamespace

from app.runtime.preflight import check_runtime_role
from app.services.worker_plane import PROFILE_QUEUE_NAME


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


def _config(*, tdlib_live_enabled: bool = False, session_roots: bool = False):
    return SimpleNamespace(
        tdlib_database_root="db-root" if session_roots else None,
        tdlib_files_root="files-root" if session_roots else None,
        tdlib_live_enabled=tdlib_live_enabled,
    )
