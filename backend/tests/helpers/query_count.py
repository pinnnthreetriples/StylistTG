"""Reusable context manager for counting SQL queries during a test.

Usage with an engine (API-level tests)::

    with QueryCounter(engine) as counter:
        client.get("/api/accounts")
    assert counter.count > 0

Usage with a session (service-level tests)::

    with QueryCounter(session) as counter:
        list_accounts(session, workspace_id=ws_id)
    assert counter.count > 0
"""

from __future__ import annotations

from typing import Union

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session


class QueryCounter:
    """Count SQL statements emitted via a SQLAlchemy Engine or Session."""

    def __init__(self, target: Union[Engine, Session]) -> None:
        if isinstance(target, Session):
            self._target: Union[Engine, Session] = target.get_bind()
        else:
            self._target = target
        self.count: int = 0
        self.queries: list[str] = []

    # --- context manager ---------------------------------------------------

    def __enter__(self) -> QueryCounter:
        event.listen(self._target, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        event.remove(self._target, "before_cursor_execute", self._callback)

    # --- listener -----------------------------------------------------------

    def _callback(
        self,
        conn,  # noqa: ANN001
        cursor,  # noqa: ANN001
        statement: str,
        parameters,  # noqa: ANN001
        context,  # noqa: ANN001
        executemany: bool,  # noqa: FBT001
    ) -> None:
        self.count += 1
        self.queries.append(statement)
