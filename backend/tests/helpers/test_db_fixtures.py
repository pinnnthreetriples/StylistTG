"""Isolation contract for the opt-in transactional DB fixtures (#268)."""

from __future__ import annotations

import pytest

from app.models import User, Workspace

# Fixtures (shared_test_engine, transactional_db_session) are auto-discovered
# via backend/tests/conftest.py — no explicit import required here.

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
    # before this test begins. The fixture intentionally disallows commit
    # (see ``test_commit_raises_dbfixture_commit_not_supported`` below).
    assert transactional_db_session.query(Workspace).count() == 0


def test_commit_raises_dbfixture_commit_not_supported(transactional_db_session) -> None:
    """Calling ``session.commit()`` on the transactional fixture must raise.

    SQLite-on-StaticPool does not fully restore connection state after a
    commit-as-savepoint-release across tests, so allowing commits would
    silently leak rows into subsequent tests. Tests that need a real
    commit must use the per-engine ``db_session`` fixture.
    """
    from tests.helpers.db_fixtures import DBFixtureCommitNotSupportedError

    _seed_workspace(transactional_db_session, "commit-not-supported")

    with pytest.raises(DBFixtureCommitNotSupportedError, match="does not support session.commit"):
        transactional_db_session.commit()
