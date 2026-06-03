"""Cross-workspace negative tests.

Verifies that a user from workspace A gets 404 (never payload, never
existence leak) when trying to access objects belonging to workspace B.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountDeletionRequest,
    AccountExportRequest,
    AccountImportBatch,
    AccountOperationLog,
    AccountStoryDraft,
    Asset,
    AssetKind,
    AssetStatus,
    AuthBatch,
    Job,
    JobState,
    SensitiveAuditEvent,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.database import create_sqlite_test_session_factory
from app.services.workspaces import ensure_default_workspace

from conftest import override_app_session

pytestmark = [pytest.mark.security, pytest.mark.api]


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _setup_two_workspaces():
    """Create workspace A (caller's context) and workspace B (foreign).

    Returns (session_factory, workspace_b_id, foreign_ids) where
    foreign_ids is a dict mapping object type to its id in workspace B.
    """
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        # Workspace A — caller's workspace (default local)
        ensure_default_workspace(session)
        session.commit()

        # Workspace B — foreign
        foreign_user = User(
            email="foreign@example.test",
            external_auth_provider="test",
            external_auth_user_id="foreign-user",
            status="active",
        )
        session.add(foreign_user)
        session.flush()

        foreign_workspace = Workspace(
            name="Foreign Workspace",
            slug="foreign-workspace",
            owner_user_id=foreign_user.id,
            status="active",
        )
        session.add(foreign_workspace)
        session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=foreign_workspace.id, user_id=foreign_user.id, role="owner"
            )
        )
        session.add(WorkspacePlan(workspace_id=foreign_workspace.id))
        session.flush()

        ws_b = foreign_workspace.id

        # Seed objects in workspace B
        foreign_account = Account(workspace_id=ws_b, external_ref="+15550001111")
        session.add(foreign_account)
        session.flush()
        account_id = foreign_account.id

        foreign_asset = Asset(
            workspace_id=ws_b,
            kind=AssetKind.PROFILE_PHOTO,
            source_path="assets/source/foreign.jpg",
            normalized_path="assets/normalized/foreign.jpg",
            content_hash="foreign-hash",
            mime="image/jpeg",
            status=AssetStatus.NORMALIZED,
        )
        session.add(foreign_asset)
        session.flush()

        foreign_job = Job(
            workspace_id=ws_b,
            account_id=account_id,
            job_state=JobState.QUEUED,
            execution_intent_hash="foreign-hash",
            job_payload_version=1,
            payload_json={"name": "Foreign"},
            plan_json_snapshot=[],
        )
        session.add(foreign_job)
        session.flush()

        foreign_draft = AccountStoryDraft(
            account_id=account_id,
            asset_id=foreign_asset.id,
            media_kind="image",
            privacy_preset="contacts",
            active_period_seconds=86400,
        )
        session.add(foreign_draft)
        session.flush()

        foreign_auth_batch = AuthBatch(
            workspace_id=ws_b,
            idempotency_key="foreign-idem-key",
            label="Foreign Batch",
            status="pending",
            total_count=1,
            max_running_commands=2,
            max_waiting_input=5,
            max_total_active=6,
        )
        session.add(foreign_auth_batch)
        session.flush()

        foreign_import_batch = AccountImportBatch(
            workspace_id=ws_b,
            source_type="json-metadata",
            status="uploaded",
        )
        session.add(foreign_import_batch)
        session.flush()

        foreign_op_log = AccountOperationLog(
            workspace_id=ws_b,
            account_id=account_id,
            operation_type="profile_update",
            status="completed",
            source="test",
            message="Foreign operation",
        )
        session.add(foreign_op_log)
        session.flush()

        foreign_audit_event = SensitiveAuditEvent(
            workspace_id=ws_b,
            action="test_action",
            entity_type="account",
            entity_id=account_id,
            account_id=account_id,
        )
        session.add(foreign_audit_event)
        session.flush()

        foreign_export = AccountExportRequest(
            workspace_id=ws_b,
            account_id=account_id,
            status="requested",
        )
        session.add(foreign_export)
        session.flush()

        foreign_deletion = AccountDeletionRequest(
            workspace_id=ws_b,
            account_id=account_id,
            status="requested",
        )
        session.add(foreign_deletion)
        session.flush()

        ids = {
            "account": account_id,
            "asset": foreign_asset.id,
            "job": foreign_job.id,
            "story_draft": foreign_draft.id,
            "auth_batch": foreign_auth_batch.id,
            "import_batch": foreign_import_batch.id,
            "operation_log": foreign_op_log.id,
            "audit_event": foreign_audit_event.id,
            "export_request": foreign_export.id,
            "deletion_request": foreign_deletion.id,
        }
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    return session_factory, ws_b, ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestCrossWorkspaceReadBlocked:
    """Foreign workspace objects must return 404, never payload."""

    def setup_method(self):
        self._sf, self._ws_b, self._ids = _setup_two_workspaces()
        self._client = TestClient(app, raise_server_exceptions=False)

    def teardown_method(self):
        self._client.close()
        app.dependency_overrides.clear()

    def test_foreign_account_returns_404(self):
        r = self._client.get(f"/api/accounts/{self._ids['account']}")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text

    def test_foreign_asset_returns_404(self):
        r = self._client.get(f"/api/assets/{self._ids['asset']}/content")
        assert r.status_code == 404
        assert self._ids["asset"] not in r.text

    def test_foreign_job_returns_404(self):
        r = self._client.get(f"/api/jobs/{self._ids['job']}")
        assert r.status_code == 404
        assert self._ids["job"] not in r.text

    # test-analyzer: disable=STG003 reason="4xx assertion without typed error body; tightened in #263"
    def test_foreign_story_drafts_returns_404_without_leaks(self):
        r = self._client.get(f"/api/story-drafts/{self._ids['account']}")
        assert r.status_code == 404, (
            f"expected 404 for foreign account story drafts, got {r.status_code}"
        )
        all_ids = [
            self._ids["story_draft"],
            self._ids["account"],
            self._ids["asset"],
        ]
        raw = r.text
        for fid in all_ids:
            assert fid not in raw, f"foreign ID {fid} leaked in response body"

    def test_foreign_auth_batch_returns_404(self):
        r = self._client.get(f"/api/auth-batches/{self._ids['auth_batch']}")
        assert r.status_code == 404
        assert self._ids["auth_batch"] not in r.text

    def test_foreign_import_batch_returns_404(self):
        r = self._client.get(f"/api/account-import-batches/{self._ids['import_batch']}")
        assert r.status_code == 404
        assert self._ids["import_batch"] not in r.text

    def test_foreign_account_operation_logs_empty(self):
        r = self._client.get(f"/api/accounts/{self._ids['account']}/operation-logs")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text

    def test_foreign_account_audit_events_empty(self):
        r = self._client.get(f"/api/accounts/{self._ids['account']}/audit-events")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text

    def test_foreign_account_export_request_404(self):
        r = self._client.get(f"/api/accounts/{self._ids['account']}/export-requests")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text

    def test_foreign_account_deletion_request_404(self):
        r = self._client.get(f"/api/accounts/{self._ids['account']}/deletion-requests")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text


@pytest.mark.security
class TestCrossWorkspaceMutationBlocked:
    """Cross-workspace mutations must return 404/403, never succeed."""

    def setup_method(self):
        self._sf, self._ws_b, self._ids = _setup_two_workspaces()
        self._client = TestClient(app, raise_server_exceptions=False)

    def teardown_method(self):
        self._client.close()
        app.dependency_overrides.clear()

    def test_cannot_create_job_for_foreign_account(self):
        r = self._client.post(
            "/api/jobs/profile",
            json={
                "account_id": self._ids["account"],
                "name": "Hijacked",
                "bio": None,
                "username": None,
                "photo_asset_id": None,
            },
        )
        assert r.status_code == 404, (
            f"expected 404 for foreign account job, got {r.status_code}: {r.text}"
        )
        assert self._ids["account"] not in r.text, "foreign account ID leaked in error response"

    def test_cannot_delete_foreign_account(self):
        r = self._client.delete(f"/api/accounts/{self._ids['account']}")
        assert r.status_code == 404
        assert self._ids["account"] not in r.text

    def test_cannot_start_foreign_auth_batch(self):
        r = self._client.post(f"/api/auth-batches/{self._ids['auth_batch']}/start")
        assert r.status_code == 404
        assert self._ids["auth_batch"] not in r.text

    def test_cannot_cancel_foreign_auth_batch(self):
        r = self._client.post(f"/api/auth-batches/{self._ids['auth_batch']}/cancel")
        assert r.status_code == 404
        assert self._ids["auth_batch"] not in r.text


@pytest.mark.security
class TestCrossWorkspaceNoExistenceLeak:
    """Error responses must not leak whether a foreign object exists."""

    def setup_method(self):
        self._sf, self._ws_b, self._ids = _setup_two_workspaces()
        self._client = TestClient(app, raise_server_exceptions=False)

    def teardown_method(self):
        self._client.close()
        app.dependency_overrides.clear()

    def test_foreign_account_error_matches_nonexistent(self):
        real_response = self._client.get(f"/api/accounts/{self._ids['account']}")
        fake_response = self._client.get("/api/accounts/00000000-0000-4000-8000-000000000999")
        assert real_response.status_code == fake_response.status_code

    def test_foreign_job_error_matches_nonexistent(self):
        real_response = self._client.get(f"/api/jobs/{self._ids['job']}")
        fake_response = self._client.get("/api/jobs/00000000-0000-4000-8000-000000000999")
        assert real_response.status_code == fake_response.status_code

    def test_foreign_auth_batch_error_matches_nonexistent(self):
        real_response = self._client.get(f"/api/auth-batches/{self._ids['auth_batch']}")
        fake_response = self._client.get("/api/auth-batches/00000000-0000-4000-8000-000000000999")
        assert real_response.status_code == fake_response.status_code
