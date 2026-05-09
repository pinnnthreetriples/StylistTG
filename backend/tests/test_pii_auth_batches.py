"""PII visibility tests for auth batch endpoints.

Verifies that:
- viewer sees phone_number=null and non-empty phone_hint != full phone
- operator/admin/owner see full phone_number
- cross-workspace batch is inaccessible
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AuthBatch,
    AuthBatchItem,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.database import create_sqlite_test_session_factory
from app.services.workspaces import ensure_default_workspace

from conftest import override_app_session


PHONE = "+15559876543"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def _setup_with_role(role: str):
    """Create env with an auth batch containing one item and return (client, batch_id, item_id)."""
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        ensure_default_workspace(session)

        account = Account(workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, external_ref=PHONE)
        session.add(account)
        session.flush()

        batch = AuthBatch(
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            idempotency_key="pii-test-batch",
            label="PII Test Batch",
            status="pending",
            total_count=1,
            max_running_commands=2,
            max_waiting_input=5,
            max_total_active=6,
        )
        session.add(batch)
        session.flush()

        item = AuthBatchItem(
            batch_id=batch.id,
            account_id=account.id,
            phone_number=PHONE,
            position=0,
        )
        session.add(item)
        session.flush()

        batch_id = batch.id
        item_id = item.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="pii-test-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role=role,
        auth_source="test",
    )
    client = TestClient(app, raise_server_exceptions=False)
    return client, batch_id, item_id


# ---------------------------------------------------------------------------
# Viewer PII tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestViewerPhoneMasking:
    """Viewer must see phone_hint but never full phone_number."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_snapshot_viewer_phone_null(self):
        client, batch_id, _ = _setup_with_role("viewer")
        r = client.get(f"/api/auth-batches/{batch_id}")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        item = items[0]
        assert item["phone_number"] is None
        assert item["phone_hint"] is not None
        assert item["phone_hint"] != PHONE
        assert len(item["phone_hint"]) > 0

    def test_poll_viewer_phone_null(self):
        client, batch_id, _ = _setup_with_role("viewer")
        r = client.get(f"/api/auth-batches/{batch_id}/poll")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        item = items[0]
        assert item["phone_number"] is None
        assert item["phone_hint"] is not None
        assert item["phone_hint"] != PHONE

    def test_viewer_hint_does_not_contain_full_phone(self):
        client, batch_id, _ = _setup_with_role("viewer")
        r = client.get(f"/api/auth-batches/{batch_id}")
        assert r.status_code == 200
        item = r.json()["items"][0]
        digits = "".join(ch for ch in PHONE if ch.isdigit())
        assert digits not in (item["phone_hint"] or "")


# ---------------------------------------------------------------------------
# Operator/Admin/Owner PII tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestOperatorSeesFullPhone:
    """Operator, admin, owner should see full phone_number."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("role", ["operator", "admin", "owner"])
    def test_snapshot_shows_full_phone(self, role):
        client, batch_id, _ = _setup_with_role(role)
        r = client.get(f"/api/auth-batches/{batch_id}")
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["phone_number"] == PHONE

    @pytest.mark.parametrize("role", ["operator", "admin", "owner"])
    def test_poll_shows_full_phone(self, role):
        client, batch_id, _ = _setup_with_role(role)
        r = client.get(f"/api/auth-batches/{batch_id}/poll")
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["phone_number"] == PHONE


# ---------------------------------------------------------------------------
# Cross-workspace
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestCrossWorkspaceBatchInaccessible:
    """Auth batch from another workspace must return 404."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_foreign_batch_returns_404(self):
        session_factory, engine = create_sqlite_test_session_factory()
        Base.metadata.create_all(engine)

        with session_factory() as session:
            ensure_default_workspace(session)

            foreign_user = User(
                email="foreign-pii@example.test",
                external_auth_provider="test",
                external_auth_user_id="foreign-pii-user",
                status="active",
            )
            session.add(foreign_user)
            session.flush()

            foreign_workspace = Workspace(
                name="Foreign PII",
                slug="foreign-pii",
                owner_user_id=foreign_user.id,
                status="active",
            )
            session.add(foreign_workspace)
            session.flush()
            session.add(WorkspaceMember(workspace_id=foreign_workspace.id, user_id=foreign_user.id, role="owner"))
            session.add(WorkspacePlan(workspace_id=foreign_workspace.id))
            session.flush()

            foreign_account = Account(workspace_id=foreign_workspace.id, external_ref=PHONE)
            session.add(foreign_account)
            session.flush()

            foreign_batch = AuthBatch(
                workspace_id=foreign_workspace.id,
                idempotency_key="foreign-pii-batch",
                label="Foreign Batch",
                status="pending",
                total_count=1,
                max_running_commands=2,
                max_waiting_input=5,
                max_total_active=6,
            )
            session.add(foreign_batch)
            session.flush()

            foreign_item = AuthBatchItem(
                batch_id=foreign_batch.id,
                account_id=foreign_account.id,
                phone_number=PHONE,
                position=0,
            )
            session.add(foreign_item)
            session.flush()
            foreign_batch_id = foreign_batch.id
            session.commit()

        override_app_session(session_factory)
        app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
            user_id="local-user",
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            role="owner",
            auth_source="test",
        )
        client = TestClient(app, raise_server_exceptions=False)
        try:
            r = client.get(f"/api/auth-batches/{foreign_batch_id}")
            assert r.status_code == 404
            assert PHONE not in r.text
        finally:
            app.dependency_overrides.clear()
