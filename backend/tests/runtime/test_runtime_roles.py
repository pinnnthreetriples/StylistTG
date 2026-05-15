from __future__ import annotations

import pytest

from app.runtime.roles import (
    assert_runtime_role_allows_queue,
    iter_runtime_roles,
    queues_for_role,
)
from app.services.worker_plane import (
    PRODUCTION_QUEUE_NAMES,
    PROFILE_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
)


def test_every_production_queue_belongs_to_runtime_role() -> None:
    assigned = {queue for role in iter_runtime_roles() for queue in role.queues}

    assert set(PRODUCTION_QUEUE_NAMES) <= assigned


def test_runtime_roles_do_not_introduce_new_queues() -> None:
    allowed = set(PRODUCTION_QUEUE_NAMES)

    assert {queue for role in iter_runtime_roles() for queue in role.queues} <= allowed


def test_api_and_reaper_consume_no_queues() -> None:
    assert queues_for_role("api") == ()
    assert queues_for_role("reaper") == ()


def test_queue_allowlist_rejects_cross_role_consumption() -> None:
    with pytest.raises(ValueError, match="cannot consume"):
        assert_runtime_role_allows_queue("warmup_dispatch_worker", PROFILE_QUEUE_NAME)

    with pytest.raises(ValueError, match="cannot consume"):
        assert_runtime_role_allows_queue("profile_worker", WARMUP_DISPATCH_QUEUE_NAME)


def test_live_tdlib_allowance_is_explicit() -> None:
    live_roles = {role.name for role in iter_runtime_roles() if role.allows_live_tdlib}

    assert live_roles == {"auth_worker", "profile_worker", "warmup_dispatch_worker"}
    for role in iter_runtime_roles():
        if role.allows_live_tdlib:
            assert role.requires_tdlib
            assert role.requires_session_storage
