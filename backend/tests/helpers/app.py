from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models import DEFAULT_LOCAL_USER_ID, DEFAULT_LOCAL_WORKSPACE_ID
from app.services.auth_context import AuthContext, get_current_auth_context


@contextmanager
def app_client(
    session_factory,
    *,
    role: str = "owner",
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    user_id: str = DEFAULT_LOCAL_USER_ID,
    auth_source: str = "test",
    raise_server_exceptions: bool = False,
) -> Iterator[TestClient]:
    def _override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id=user_id,
        workspace_id=workspace_id,
        role=role,
        auth_source=auth_source,
    )
    try:
        with TestClient(app, raise_server_exceptions=raise_server_exceptions) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
