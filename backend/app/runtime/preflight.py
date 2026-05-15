from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.runtime.roles import RuntimeRole, get_runtime_role


class RuntimeSettings(Protocol):
    @property
    def tdlib_database_root(self) -> object | None: ...

    @property
    def tdlib_files_root(self) -> object | None: ...

    @property
    def tdlib_live_enabled(self) -> bool: ...


@dataclass(frozen=True)
class RuntimeRolePreflightRead:
    role_name: str
    known: bool
    allowed_queues: tuple[str, ...]
    queue_violations: tuple[str, ...]
    requires_tdlib: bool
    requires_session_storage: bool
    allows_live_tdlib: bool
    tdlib_live_enabled: bool
    session_root_configured: bool
    errors: tuple[str, ...]


def check_runtime_role(
    role_name: str,
    *,
    queues: tuple[str, ...] = (),
    config: RuntimeSettings = settings,
) -> RuntimeRolePreflightRead:
    try:
        role = get_runtime_role(role_name)
    except ValueError as exc:
        return RuntimeRolePreflightRead(
            role_name=role_name,
            known=False,
            allowed_queues=(),
            queue_violations=queues,
            requires_tdlib=False,
            requires_session_storage=False,
            allows_live_tdlib=False,
            tdlib_live_enabled=bool(config.tdlib_live_enabled),
            session_root_configured=check_session_root_policy(None, config=config),
            errors=(str(exc),),
        )

    queue_violations = check_queue_allowlist(role, queues)
    errors: list[str] = []
    if queue_violations:
        errors.extend(
            f"queue not allowed for role {role.name}: {queue}" for queue in queue_violations
        )
    if role.requires_session_storage and not check_session_root_policy(role, config=config):
        errors.append("tdlib session root is not configured")
    if role.requires_tdlib and not check_tdlib_runtime_available(role, config=config):
        errors.append("tdlib runtime is required but live TDLib is disabled")

    return RuntimeRolePreflightRead(
        role_name=role.name,
        known=True,
        allowed_queues=role.queues,
        queue_violations=queue_violations,
        requires_tdlib=role.requires_tdlib,
        requires_session_storage=role.requires_session_storage,
        allows_live_tdlib=role.allows_live_tdlib,
        tdlib_live_enabled=bool(config.tdlib_live_enabled),
        session_root_configured=check_session_root_policy(role, config=config),
        errors=tuple(errors),
    )


def check_tdlib_runtime_available(
    role: RuntimeRole | None,
    *,
    config: RuntimeSettings = settings,
) -> bool:
    if role is None or not role.requires_tdlib:
        return True
    return bool(config.tdlib_live_enabled)


def check_session_root_policy(
    role: RuntimeRole | None,
    *,
    config: RuntimeSettings = settings,
) -> bool:
    configured = bool(config.tdlib_database_root and config.tdlib_files_root)
    if role is None or not role.requires_session_storage:
        return configured
    return configured


def check_queue_allowlist(role: RuntimeRole, queues: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(queue for queue in queues if queue not in role.queues)
