"""PR 8: Tests for operation log workspace boundaries and export expiry."""
from __future__ import annotations

import pytest

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, AccountState
from app.services.account_lifecycle import (
    create_account_export_request,
    list_deletion_requests,
    list_export_requests,
    request_account_deletion,
)
from app.services.accounts import create_account
from app.services.operation_logs import list_account_logs, list_global_logs, log_operation


class FakeStorage:
    def save_bytes(self, key, content, **_):
        return object()


def test_log_operation_with_explicit_workspace_id(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200001")
    row = log_operation(
        db_session,
        account_id=account.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="explicit workspace",
        workspace_id="ws-explicit",
    )
    db_session.flush()

    assert row.workspace_id == "ws-explicit"


def test_log_operation_fallback_derives_workspace_from_account(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200002")
    row = log_operation(
        db_session,
        account_id=account.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="fallback workspace",
    )
    db_session.flush()

    assert row.workspace_id == account.workspace_id


def test_log_operation_fallback_unknown_account_uses_default(db_session) -> None:
    row = log_operation(
        db_session,
        account_id="nonexistent-account-id",
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="unknown account fallback",
    )
    db_session.flush()

    assert row.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID


def test_list_account_logs_filters_by_workspace(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200003")
    log_operation(
        db_session,
        account_id=account.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="visible log",
        workspace_id=account.workspace_id,
    )
    log_operation(
        db_session,
        account_id=account.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="another log",
        workspace_id=account.workspace_id,
    )
    db_session.commit()

    own_logs = list_account_logs(db_session, account.id, workspace_id=account.workspace_id)
    assert own_logs["total"] == 2

    with pytest.raises(ValueError, match="account not found"):
        list_account_logs(db_session, account.id, workspace_id="ws-foreign")


def test_wrong_workspace_cannot_list_account_logs(db_session) -> None:
    account_a = create_account(db_session, external_ref="+15550200004")
    log_operation(
        db_session,
        account_id=account_a.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="a log",
        workspace_id=account_a.workspace_id,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="account not found"):
        list_account_logs(db_session, account_a.id, workspace_id="ws-wrong")


def test_global_logs_scoped_by_workspace(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200006")
    log_operation(
        db_session,
        account_id=account.id,
        operation_type="test",
        status="completed",
        severity="info",
        source="test",
        message="global scoped",
        workspace_id="ws-scoped",
    )
    db_session.commit()

    scoped = list_global_logs(db_session, workspace_id="ws-scoped")
    assert scoped["total"] == 1

    other = list_global_logs(db_session, workspace_id="ws-nope")
    assert other["total"] == 0


def test_export_request_has_expiry(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200007")
    db_session.commit()

    request = create_account_export_request(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        actor_user_id=None,
        storage=FakeStorage(),
    )

    assert request.expires_at is not None
    assert request.completed_at is not None
    assert request.expires_at > request.completed_at


def test_export_request_is_workspace_scoped(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200008")
    db_session.commit()

    create_account_export_request(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        actor_user_id=None,
        storage=FakeStorage(),
    )

    own = list_export_requests(db_session, account_id=account.id, workspace_id=account.workspace_id)
    assert len(own) == 1

    with pytest.raises(ValueError, match="account not found"):
        list_export_requests(db_session, account_id=account.id, workspace_id="ws-foreign")


def test_deletion_request_is_workspace_scoped(db_session) -> None:
    account = create_account(db_session, external_ref="+15550200009")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    request_account_deletion(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        actor_user_id=None,
        reason="test deletion request for workspace scoping",
        confirmation="DELETE",
        dry_run=True,
    )

    own = list_deletion_requests(db_session, account_id=account.id, workspace_id=account.workspace_id)
    assert len(own) == 1

    with pytest.raises(ValueError, match="account not found"):
        list_deletion_requests(db_session, account_id=account.id, workspace_id="ws-foreign")
