"""Opt-in fast DB fixtures with strong isolation (issue #268).

The default :func:`tests.conftest.db_session` fixture creates a fresh
in-memory SQLite engine and full schema per test. That is the safest
default but rebuilds the schema for every test.

This module provides two opt-in fixtures that keep isolation while
reducing setup cost:

- :func:`shared_test_engine` (session-scoped): creates the schema **once**
  per pytest session.
- :func:`transactional_db_session` (function-scoped): wraps each test in
  a SAVEPOINT-backed transaction that is rolled back at teardown, so the
  schema can be reused without cross-test leakage.

Migrating an existing test from the per-test engine to the transactional
fixture is a drop-in rename in most cases::

    def test_thing(transactional_db_session):
        # behaves like db_session but ~5× cheaper to set up.
        ...

Tests that call ``session.commit()`` (and rely on the commit being
durably observable from a *different* engine) must keep using the
default :func:`tests.conftest.db_session` per-engine fixture. With this
SAVEPOINT-backed fixture the SQLite-on-StaticPool combination does not
fully restore connection state after a savepoint release across tests.

Reference: pytest fixture scopes — https://docs.pytest.org/en/stable/how-to/fixtures.html
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base


@pytest.fixture(scope="session")
def shared_test_engine() -> Iterator[Engine]:
    """Session-scoped SQLite engine. Schema is created once per pytest run."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def transactional_db_session(shared_test_engine: Engine) -> Iterator[Session]:
    """Function-scoped Session wrapped in a SAVEPOINT-backed transaction.

    Strategy follows the SQLAlchemy "Joining a Session into an External
    Transaction" pattern: open a connection, begin an outer transaction,
    bind a session to that connection, and roll the outer transaction
    back at teardown. ``session.commit()`` is intercepted by SQLAlchemy
    and turned into a SAVEPOINT release, so the underlying outer
    transaction stays open and the rollback at teardown is total.
    """
    connection = shared_test_engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()
