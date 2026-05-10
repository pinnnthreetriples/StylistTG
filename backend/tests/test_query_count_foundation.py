"""Foundation tests for query-count tooling."""

from __future__ import annotations

import pytest

from app.models import Account
from app.services.accounts import create_account

from tests.helpers.factories import make_session
from tests.helpers.query_count import QueryCounter

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    return make_session()


def test_query_counter_counts_service_calls():
    """QueryCounter captures queries when used with a session."""
    sf, engine = _make_session()
    with sf() as session:
        create_account(session, external_ref="+15550100001")

    with sf() as session:
        with QueryCounter(engine) as counter:
            session.execute(Account.__table__.select())
        assert counter.count > 0, "QueryCounter must capture at least one query"


def test_query_counter_resets_between_contexts():
    """Each QueryCounter context starts at zero."""
    sf, engine = _make_session()
    with sf() as session:
        create_account(session, external_ref="+15550100002")

    with sf() as session:
        with QueryCounter(engine) as c1:
            session.execute(Account.__table__.select())
        first = c1.count

        with QueryCounter(engine) as c2:
            session.execute(Account.__table__.select())
        assert c2.count == first
        assert c1.count == first  # c1 stopped counting
