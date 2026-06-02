"""Isolation contract for the opt-in transactional DB fixtures (#268)."""

from __future__ import annotations

import pytest

from app.models import User, Workspace
from tests.helpers.db_fixtures import shared_test_engine, transactional_db_session  # noqa: F401

pytestmark = pytest.mark.unit


def _seed_workspace(session, slug: str) -> Workspace:
    user = User(
        email=f"owner-{slug}@example.test",
        external_auth_provider="local",
        external_auth_user_id=f"local-{slug}",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(name=slug, slug=slug, owner_user_id=user.id)
    session.add(workspace)
    session.flush()
    return workspace


def test_transactional_session_rolls_back_inserts(transactional_db_session) -> None:
    _seed_workspace(transactional_db_session, "iso-1")

    assert transactional_db_session.query(Workspace).filter_by(slug="iso-1").count() == 1


def test_transactional_session_isolates_from_previous_test(transactional_db_session) -> None:
    # The row inserted by `test_transactional_session_rolls_back_inserts` must
    # not be visible here — SAVEPOINT rollback is the whole point of the fixture.
    assert transactional_db_session.query(Workspace).filter_by(slug="iso-1").count() == 0


def test_flushed_but_uncommitted_writes_do_not_leak(transactional_db_session) -> None:
    # Sanity: an uncommitted write made by a previous test is rolled back
    # before this test begins. (Tests that explicitly call .commit() should
    # not use this fixture — see the docstring on transactional_db_session.)
    assert transactional_db_session.query(Workspace).count() == 0
