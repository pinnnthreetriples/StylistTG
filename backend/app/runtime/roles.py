from __future__ import annotations

from dataclasses import dataclass

from app.services.worker_plane import (
    ACCOUNT_LIFECYCLE_QUEUE_NAME,
    AUTH_QUEUE_NAME,
    MAINTENANCE_QUEUE_NAME,
    MEDIA_QUEUE_NAME,
    NEURO_COMMENT_QUEUE_NAME,
    PROFILE_QUEUE_NAME,
    PRODUCTION_QUEUE_NAMES,
    SCHEDULER_QUEUE_NAME,
    STORY_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
)


@dataclass(frozen=True)
class RuntimeRole:
    name: str
    queues: tuple[str, ...]
    requires_tdlib: bool
    requires_session_storage: bool
    allows_live_tdlib: bool
    description: str


RUNTIME_ROLES: tuple[RuntimeRole, ...] = (
    RuntimeRole(
        name="api",
        queues=(),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="FastAPI request handling without worker queue consumption.",
    ),
    RuntimeRole(
        name="scheduler",
        queues=(SCHEDULER_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Scheduled enqueue decisions and lightweight scheduler jobs.",
    ),
    RuntimeRole(
        name="reaper",
        queues=(),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Out-of-band stale job reconciliation without queue consumption.",
    ),
    RuntimeRole(
        name="auth_worker",
        queues=(AUTH_QUEUE_NAME,),
        requires_tdlib=True,
        requires_session_storage=True,
        allows_live_tdlib=True,
        description="Telegram auth and reauth worker.",
    ),
    RuntimeRole(
        name="profile_worker",
        queues=(PROFILE_QUEUE_NAME,),
        requires_tdlib=True,
        requires_session_storage=True,
        allows_live_tdlib=True,
        description="Profile/account update worker.",
    ),
    RuntimeRole(
        name="warmup_worker",
        queues=(WARMUP_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Dry-run account preparation worker.",
    ),
    RuntimeRole(
        name="warmup_dispatch_worker",
        queues=(WARMUP_DISPATCH_QUEUE_NAME,),
        requires_tdlib=True,
        requires_session_storage=True,
        allows_live_tdlib=True,
        description="Warmup micro-session dispatch worker.",
    ),
    RuntimeRole(
        name="neuro_comment_worker",
        queues=(NEURO_COMMENT_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Safe neuro-commenting generation and manual approval worker.",
    ),
    RuntimeRole(
        name="maintenance_worker",
        queues=(MAINTENANCE_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Maintenance worker for generic maintenance jobs.",
    ),
    RuntimeRole(
        name="media_worker",
        queues=(MEDIA_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Media processing worker.",
    ),
    RuntimeRole(
        name="story_worker",
        queues=(STORY_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Story queue worker for reserved story jobs.",
    ),
    RuntimeRole(
        name="account_lifecycle_worker",
        queues=(ACCOUNT_LIFECYCLE_QUEUE_NAME,),
        requires_tdlib=False,
        requires_session_storage=False,
        allows_live_tdlib=False,
        description="Account lifecycle worker.",
    ),
)

_ROLES_BY_NAME = {role.name: role for role in RUNTIME_ROLES}


def iter_runtime_roles() -> tuple[RuntimeRole, ...]:
    return RUNTIME_ROLES


def get_runtime_role(role_name: str) -> RuntimeRole:
    try:
        return _ROLES_BY_NAME[role_name]
    except KeyError as exc:
        raise ValueError(f"unknown runtime role: {role_name}") from exc


def queues_for_role(role_name: str) -> tuple[str, ...]:
    return get_runtime_role(role_name).queues


def assert_runtime_role_allows_queue(role_name: str, queue_name: str) -> None:
    role = get_runtime_role(role_name)
    if queue_name not in PRODUCTION_QUEUE_NAMES:
        raise ValueError(f"unsupported worker queue: {queue_name}")
    if queue_name not in role.queues:
        raise ValueError(f"runtime role {role_name} cannot consume queue: {queue_name}")
