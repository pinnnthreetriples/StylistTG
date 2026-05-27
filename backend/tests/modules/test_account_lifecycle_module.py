from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from app.errors import AppError
from app.modules.account_lifecycle import contracts
from app.modules.auth.context import AuthContext
from app.modules.registry import iter_modules


def test_account_lifecycle_module_is_registered_as_public_boundary() -> None:
    module = next(module for module in iter_modules() if module.name == "account_lifecycle")

    assert module.router_path == "app.modules.account_lifecycle.router:router"
    assert module.workflows == ()


def test_account_lifecycle_legacy_wrappers_alias_canonical_modules() -> None:
    aliases = {
        "app.api.account_lifecycle_routes": "app.modules.account_lifecycle.router",
        "app.services.account_lifecycle": "app.modules.account_lifecycle.service",
        "app.services.retention_worker": "app.modules.account_lifecycle.retention",
    }

    assert {
        legacy: importlib.import_module(legacy) is importlib.import_module(canonical)
        for legacy, canonical in aliases.items()
    } == dict.fromkeys(aliases, True)


def test_account_lifecycle_contracts_are_module_owned() -> None:
    contracts = importlib.import_module("app.modules.account_lifecycle.contracts")

    assert contracts.AccountDeletionPreviewRead.__name__ == "AccountDeletionPreviewRead"
    assert contracts.AccountExportRequestRead.__name__ == "AccountExportRequestRead"


@pytest.mark.parametrize(
    ("confirmation", "reason", "message"),
    [
        ("WRONG", "operator requested cleanup", "confirmation required"),
        ("DELETE", "short", "reason too short"),
    ],
)
def test_account_lifecycle_service_rejects_invalid_deletion_requests(
    confirmation: str,
    reason: str,
    message: str,
) -> None:
    service = importlib.import_module("app.modules.account_lifecycle.service")

    with pytest.raises(ValueError, match=message):
        service.request_account_deletion(
            object(),
            account_id="account-1",
            workspace_id="workspace-1",
            actor_user_id="user-1",
            reason=reason,
            confirmation=confirmation,
            dry_run=True,
        )


def test_account_lifecycle_router_maps_deletion_request_not_found(monkeypatch) -> None:
    router = importlib.import_module("app.modules.account_lifecycle.router")
    auth = AuthContext(
        user_id="user-1", workspace_id="workspace-1", role="operator", auth_source="test"
    )
    payload = contracts.AccountDeletionRequestCreate(
        reason="operator requested cleanup", confirmation="DELETE"
    )

    def raise_not_found(*_args, **_kwargs):
        raise ValueError("account not found")

    monkeypatch.setattr(router, "request_account_deletion", raise_not_found)

    with pytest.raises(AppError) as exc_info:
        router.post_account_deletion_request("account-1", payload, object(), auth)

    assert exc_info.value.error_code == "ACCOUNT_NOT_FOUND"


def test_account_lifecycle_router_maps_deletion_request_rejection(monkeypatch) -> None:
    router = importlib.import_module("app.modules.account_lifecycle.router")
    auth = AuthContext(
        user_id="user-1", workspace_id="workspace-1", role="operator", auth_source="test"
    )
    payload = contracts.AccountDeletionRequestCreate(
        reason="operator requested cleanup", confirmation="DELETE"
    )

    def raise_rejected(*_args, **_kwargs):
        raise ValueError("active deletion request exists")

    monkeypatch.setattr(router, "request_account_deletion", raise_rejected)

    with pytest.raises(AppError) as exc_info:
        router.post_account_deletion_request("account-1", payload, object(), auth)

    assert exc_info.value.error_code == "ACCOUNT_DELETION_REJECTED"


def test_account_lifecycle_router_maps_missing_individual_requests(monkeypatch) -> None:
    router = importlib.import_module("app.modules.account_lifecycle.router")
    auth = AuthContext(
        user_id="user-1", workspace_id="workspace-1", role="operator", auth_source="test"
    )
    monkeypatch.setattr(router, "get_deletion_request", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(router, "get_export_request", lambda *_args, **_kwargs: None)

    with pytest.raises(AppError) as deletion_exc:
        router.get_account_deletion_request("account-1", "request-1", object(), auth)
    with pytest.raises(AppError) as export_exc:
        router.get_account_export_request("account-1", "request-1", object(), auth)

    assert deletion_exc.value.error_code == "DELETION_REQUEST_NOT_FOUND"
    assert export_exc.value.error_code == "EXPORT_REQUEST_NOT_FOUND"


def test_account_lifecycle_router_returns_individual_requests(monkeypatch) -> None:
    router = importlib.import_module("app.modules.account_lifecycle.router")
    auth = AuthContext(
        user_id="user-1", workspace_id="workspace-1", role="operator", auth_source="test"
    )
    deletion_request = SimpleNamespace(
        id="delete-1",
        account_id="account-1",
        status="previewed",
        reason="operator requested cleanup",
        dry_run_result_json={},
        execution_result_json=None,
        requested_at="2026-05-27T00:00:00Z",
        completed_at=None,
        failed_at=None,
        failure_code=None,
        failure_message=None,
    )
    export_request = SimpleNamespace(
        id="export-1",
        account_id="account-1",
        status="completed",
        export_key="private-key",
        export_size_bytes=12,
        export_content_type="application/json",
        requested_at="2026-05-27T00:00:00Z",
        completed_at="2026-05-27T00:00:00Z",
        failed_at=None,
        failure_code=None,
        failure_message=None,
        expires_at="2026-05-28T00:00:00Z",
    )
    monkeypatch.setattr(router, "get_deletion_request", lambda *_args, **_kwargs: deletion_request)
    monkeypatch.setattr(router, "get_export_request", lambda *_args, **_kwargs: export_request)

    deletion_read = router.get_account_deletion_request("account-1", "delete-1", object(), auth)
    export_read = router.get_account_export_request("account-1", "export-1", object(), auth)

    assert deletion_read.id == "delete-1"
    assert export_read.id == "export-1"
    assert export_read.export_key == "[private]"
