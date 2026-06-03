from __future__ import annotations

import base64
import io
from datetime import timedelta
from zipfile import ZipFile, ZipInfo

import pytest

from app.config import settings
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountOnboardingArtifact,
    AccountOnboardingBatch,
    AccountOnboardingEvent,
    AccountOnboardingItem,
    IdempotencyKey,
    Workspace,
    new_id,
    utc_now,
)
from app.modules.account_onboarding import service as onboarding_service
from app.modules.account_onboarding import artifacts as onboarding_artifacts


@pytest.fixture(autouse=True)
def _account_onboarding_storage_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_local_root", tmp_path / "storage")


def test_account_onboarding_phone_batch_validates_as_canonical_flow(app_client) -> None:
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "onboarding-create-1",
            "source_type": "phone",
            "label": "June",
            "phone_items": [{"phone_number": "+1 (555) 010-2000", "label": "A"}],
        },
    )

    assert create.status_code == 201
    batch_id = create.json()["batch"]["id"]
    validate = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "onboarding-validate-1"},
    )

    assert validate.status_code == 200
    body = validate.json()
    assert body["batch"]["source_type"] == "phone_bulk"
    assert body["batch"]["status"] == "preview_ready"
    assert body["items"][0]["status"] == "requires_reauth"
    assert body["items"][0]["validation_code"] == "phone_requires_live_auth"
    assert body["items"][0]["phone_hint"] == "***2000"
    assert "phone_number" not in body["items"][0]


def test_account_onboarding_confirm_requires_consent(app_client) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "onboarding-create-2",
            "source_type": "json_metadata",
            "metadata_json": {"username": "demo"},
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "onboarding-validate-2"},
    )

    response = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "onboarding-confirm-2",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": False,
            "consent_version": "v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "ONBOARDING_CONSENT_REQUIRED"
    assert response.json()["details"]["request_id"] == response.json()["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_account_onboarding_artifact_rejects_zip_slip_and_hides_object_key(app_client) -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../tdlib/session", "unsafe")

    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-unsafe-1",
        content_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "ONBOARDING_ARTIFACT_UNSAFE"
    assert "object_key" not in response.text


def test_account_onboarding_artifact_rejects_absolute_archive_paths(app_client) -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("/tdlib/session", "unsafe")

    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-absolute-1",
        content_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_unsafe_path"


def test_account_onboarding_artifact_rejects_invalid_base64(app_client) -> None:
    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-invalid-base64",
        content_base64="not-base64!",
    )

    assert response.status_code == 422
    assert "content_base64" in response.text


def test_account_onboarding_artifact_rejects_archive_symlink(app_client) -> None:
    buffer = io.BytesIO()
    info = ZipInfo("tdlib/link")
    info.external_attr = 0o120777 << 16
    with ZipFile(buffer, "w") as archive:
        archive.writestr(info, "target")

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-symlink",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_symlink"


def test_account_onboarding_artifact_rejects_too_many_archive_files(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_FILES", 1)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-many-files",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"a": "1", "b": "2"})).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_many_files"


def test_account_onboarding_artifact_rejects_too_deep_archive(app_client, monkeypatch) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_DEPTH", 2)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-deep",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"a/b/c": "deep"})).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_deep"


def test_account_onboarding_artifact_rejects_too_large_uncompressed_archive(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 4)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-large-expanded",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "too-large"})).decode(
                "ascii"
            ),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_large"


def test_account_onboarding_artifact_success_response_is_frontend_safe(app_client) -> None:
    encoded = base64.b64encode(b'{"session":"redacted fixture"}').decode("ascii")

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-safe-response-1",
            "source_type": "session_file",
            "filename": "fixture.session.json",
            "content_base64": encoded,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "quarantined"
    assert "object_key" not in body
    assert "path" not in response.text


def test_account_onboarding_tdlib_artifact_rejects_non_zip(app_client) -> None:
    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "tdlib-non-zip-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.bin",
            "content_base64": base64.b64encode(b"not a zip").decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_required"


def test_account_onboarding_artifact_rejects_large_base64_before_decode(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARTIFACT_BASE64_CHARS", 4)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-encoded-too-large",
            "source_type": "session_file",
            "filename": "fixture.session.json",
            "content_base64": "QUFBQUE=",
        },
    )

    assert response.status_code == 413
    assert response.json()["error_code"] == "ONBOARDING_ARTIFACT_TOO_LARGE"


def test_account_onboarding_session_file_unknown_format_is_unsupported(app_client) -> None:
    upload = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "session-file-unknown-upload",
            "source_type": "session_file",
            "filename": "unknown.bin",
            "content_base64": base64.b64encode(b"unknown").decode("ascii"),
        },
    )
    artifact_id = upload.json()["id"]
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "session-file-unknown-create",
            "source_type": "session_file",
            "artifact_id": artifact_id,
            "filename": "unknown.bin",
        },
    ).json()

    response = app_client.post(
        f"/api/account-onboarding-batches/{create['batch']['id']}/validate",
        json={"idempotency_key": "session-file-unknown-validate"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "unsupported"
    assert item["validation_code"] == "session_file_unsupported"


def test_account_onboarding_json_metadata_scalar_is_blocked(app_client) -> None:
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-invalid-create",
            "source_type": "json_metadata",
            "metadata_json": "not-an-object",
        },
    ).json()

    response = app_client.post(
        f"/api/account-onboarding-batches/{create['batch']['id']}/validate",
        json={"idempotency_key": "metadata-invalid-validate"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "blocked"
    assert item["validation_code"] == "metadata_invalid"


def test_account_onboarding_json_metadata_extracts_phone_hint(app_client) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-phone-hint-create",
            "source_type": "json_metadata",
            "metadata_json": {"username": "demo", "phone_number": "+15550102000"},
        },
    ).json()

    response = app_client.post(
        f"/api/account-onboarding-batches/{created['batch']['id']}/validate",
        json={"idempotency_key": "metadata-phone-hint-validate"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["phone_hint"] == "***2000"


def test_account_onboarding_json_metadata_array_within_limit_works(app_client) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-array-create",
            "source_type": "json_metadata",
            "metadata_json": [{"username": "demo-a"}, {"phone": "+15550102000"}],
        },
    )

    assert created.status_code == 201
    assert created.json()["batch"]["counters"]["total_count"] == 2


def test_account_onboarding_json_metadata_rejects_too_many_items(app_client) -> None:
    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-too-many-create",
            "source_type": "json_metadata",
            "metadata_json": [{"username": f"user-{index}"} for index in range(501)],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert response.json()["field_errors"][0]["field"] == "metadata_json"


def test_account_onboarding_json_metadata_rejects_too_large_payload(app_client) -> None:
    sensitive_value = "secret-metadata-value"
    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-too-large-create",
            "source_type": "json_metadata",
            "metadata_json": {"username": "demo", "blob": sensitive_value * 20_000},
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert response.json()["details"]["errors"][0]["input"] == "[redacted]"
    assert sensitive_value not in response.text


def test_account_onboarding_default_tdlib_capability_is_not_full_support(app_client) -> None:
    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "tdlib-capability-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    )

    assert response.status_code == 201
    capabilities = {item["source_type"]: item for item in response.json()["capabilities"]}
    assert capabilities["phone_bulk"]["can_materialize_session"] is False
    assert capabilities["phone_bulk"]["user_facing_support_level"] == "requires_reauth"
    assert capabilities["tdlib_directory"]["can_materialize_session"] is False
    assert capabilities["tdlib_directory"]["user_facing_support_level"] == "preview_only"


def test_account_onboarding_create_rejects_missing_artifact(app_client) -> None:
    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "missing-artifact-create",
            "source_type": "tdlib_directory",
            "artifact_id": "00000000-0000-4000-8000-000000000001",
            "filename": "tdlib.zip",
        },
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "ONBOARDING_ARTIFACT_NOT_FOUND"


def test_account_onboarding_create_rejects_cross_workspace_artifact(app_client, db_session) -> None:
    foreign_workspace = Workspace(
        name="Foreign artifact",
        slug="foreign-artifact",
        owner_user_id=DEFAULT_LOCAL_USER_ID,
    )
    db_session.add(foreign_workspace)
    db_session.flush()
    artifact = _artifact_row(workspace_id=foreign_workspace.id, source_type="tdlib_directory")
    db_session.add(artifact)
    db_session.commit()

    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "foreign-artifact-create",
            "source_type": "tdlib_directory",
            "artifact_id": artifact.id,
            "filename": "tdlib.zip",
        },
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "ONBOARDING_ARTIFACT_NOT_FOUND"


def test_account_onboarding_create_rejects_artifact_source_mismatch(app_client) -> None:
    uploaded = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "source-mismatch-upload",
            "source_type": "session_file",
            "filename": "fixture.session.json",
            "content_base64": base64.b64encode(b'{"session":"fixture"}').decode("ascii"),
        },
    ).json()

    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "source-mismatch-create",
            "source_type": "tdlib_directory",
            "artifact_id": uploaded["id"],
            "filename": "tdlib.zip",
        },
    )

    assert response.status_code == 409
    assert response.json()["details"]["validation_code"] == "artifact_source_mismatch"


def test_account_onboarding_create_rejects_already_attached_artifact(app_client) -> None:
    uploaded = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "double-attach-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "safe"})).decode(
                "ascii"
            ),
        },
    ).json()
    first = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "double-attach-first-create",
            "source_type": "tdlib_directory",
            "artifact_id": uploaded["id"],
            "filename": "tdlib.zip",
        },
    )

    second = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "double-attach-second-create",
            "source_type": "tdlib_directory",
            "artifact_id": uploaded["id"],
            "filename": "tdlib.zip",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["details"]["validation_code"] == "artifact_already_attached"


def test_account_onboarding_create_idempotency_returns_cached_after_artifact_rejected(
    app_client, db_session
) -> None:
    uploaded = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "cached-after-reject-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "safe"})).decode(
                "ascii"
            ),
        },
    ).json()
    payload = {
        "idempotency_key": "cached-after-reject-create",
        "source_type": "tdlib_directory",
        "artifact_id": uploaded["id"],
        "filename": "tdlib.zip",
    }
    first = app_client.post("/api/account-onboarding-batches", json=payload)
    artifact = db_session.get(AccountOnboardingArtifact, uploaded["id"])
    assert artifact is not None
    artifact.status = "rejected"
    db_session.commit()

    second = app_client.post("/api/account-onboarding-batches", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["batch"]["id"] == first.json()["batch"]["id"]


def test_account_onboarding_validate_rejects_artifact_that_became_rejected(
    app_client, db_session
) -> None:
    uploaded = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "stale-artifact-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "safe"})).decode(
                "ascii"
            ),
        },
    ).json()
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "stale-artifact-create",
            "source_type": "tdlib_directory",
            "artifact_id": uploaded["id"],
            "filename": "tdlib.zip",
        },
    ).json()
    artifact = db_session.get(AccountOnboardingArtifact, uploaded["id"])
    assert artifact is not None
    artifact.status = "rejected"
    db_session.commit()

    response = app_client.post(
        f"/api/account-onboarding-batches/{created['batch']['id']}/validate",
        json={"idempotency_key": "stale-artifact-validate"},
    )

    assert response.status_code == 409
    assert response.json()["details"]["validation_code"] == "artifact_status_unusable"


def test_account_onboarding_create_idempotency_conflict(app_client) -> None:
    payload = {
        "idempotency_key": "onboarding-create-conflict",
        "source_type": "phone",
        "phone_items": [{"phone_number": "+15550102000"}],
    }
    first = app_client.post("/api/account-onboarding-batches", json=payload)
    second = app_client.post(
        "/api/account-onboarding-batches",
        json={**payload, "phone_items": [{"phone_number": "+15550102001"}]},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error_code"] == "ONBOARDING_INVALID_STATE"


def test_account_onboarding_create_accepts_max_length_idempotency_key(
    app_client, db_session
) -> None:
    idempotency_key = "x" * 128
    payload = {
        "idempotency_key": idempotency_key,
        "source_type": "phone",
        "phone_items": [{"phone_number": "+15550102000"}],
    }

    first = app_client.post("/api/account-onboarding-batches", json=payload)
    second = app_client.post("/api/account-onboarding-batches", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    row = (
        db_session.query(IdempotencyKey)
        .filter_by(entity_id=first.json()["batch"]["id"], operation="create_batch")
        .one()
    )

    assert second.json()["batch"]["id"] == first.json()["batch"]["id"]
    assert len(row.key) <= 128
    assert idempotency_key not in row.key


def test_account_onboarding_queue_unavailable_persists_safe_failure(
    app_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: False)
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "queue-unavailable-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "queue-unavailable-validate"},
    )
    item = db_session.get(AccountOnboardingItem, created["items"][0]["id"])
    assert item is not None
    item.status = "valid"
    item.requires_reauth = False
    item.validation_code = None
    item.validation_message = "Ready for queue failure test."
    db_session.commit()

    confirm = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "queue-unavailable-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    )
    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")

    assert confirm.status_code == 503
    assert detail.json()["batch"]["status"] == "failed"
    assert detail.json()["items"][0]["status"] == "failed"
    assert "next_retry_at" in detail.json()["items"][0]
    assert "phone_number" not in detail.text


def test_account_onboarding_retry_denied_when_cooldown_active(app_client, db_session) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "retry-cooldown-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    item_id = created["items"][0]["id"]
    item = db_session.get(AccountOnboardingItem, item_id)
    assert item is not None
    item.status = "failed"
    item.last_error_code = "tdlib_unavailable"
    item.next_retry_at = utc_now() + timedelta(seconds=60)
    db_session.commit()

    response = app_client.post(
        f"/api/account-onboarding-batches/{created['batch']['id']}/items/{item_id}/retry",
        json={"idempotency_key": "retry-cooldown-attempt"},
    )

    assert response.status_code == 429
    assert response.json()["error_code"] == "ONBOARDING_RATE_LIMITED"
    assert response.json()["details"]["retry_after_seconds"] > 0
    assert response.json()["details"]["request_id"] == response.json()["request_id"]


def test_account_onboarding_phone_preview_is_honest_about_manual_auth(
    app_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: True)
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "auth-session-link-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000", "label": "Primary"}],
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "auth-session-link-validate"},
    )
    confirmed = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "auth-session-link-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    ).json()
    item_id = confirmed["items"][0]["id"]

    item = onboarding_service.execute_item(db_session, item_id=item_id)
    assert item.auth_session_id is None
    assert item.status == "requires_reauth"

    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")
    body = detail.json()
    assert body["batch"]["status"] == "requires_reauth"
    assert body["items"][0]["auth_session_id"] is None
    assert body["items"][0]["validation_code"] == "phone_requires_live_auth"
    assert "tdlib_storage_key" not in detail.text
    assert item_id == body["items"][0]["id"]


def test_account_onboarding_phone_execute_does_not_create_fake_auth_session(
    app_client, db_session
) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "phone-no-fake-auth-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000", "label": "Primary"}],
        },
    ).json()
    item = db_session.get(AccountOnboardingItem, created["items"][0]["id"])
    batch = db_session.get(AccountOnboardingBatch, created["batch"]["id"])
    assert item is not None
    assert batch is not None
    batch.consent_confirmed_at = utc_now()
    batch.status = "queued"
    item.status = "queued"
    db_session.commit()

    executed = onboarding_service.execute_item(db_session, item_id=item.id)

    assert executed.status == "requires_reauth"
    assert executed.auth_session_id is None
    assert executed.last_error_code == "phone_requires_live_auth"


def test_account_onboarding_tdlib_preview_requires_reauth_without_verifier(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: True)
    upload = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "tdlib-exec-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "safe"})).decode(
                "ascii"
            ),
        },
    ).json()
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "tdlib-exec-create",
            "source_type": "tdlib_directory",
            "artifact_id": upload["id"],
            "filename": "tdlib.zip",
        },
    ).json()
    batch_id = created["batch"]["id"]
    validated = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "tdlib-exec-validate"},
    ).json()
    assert validated["items"][0]["status"] == "requires_reauth"
    assert validated["items"][0]["validation_code"] == "tdlib_artifact_verifier_not_enabled"
    confirmed = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "tdlib-exec-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    ).json()
    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")

    assert confirmed["batch"]["status"] == "requires_reauth"
    assert detail.json()["items"][0]["status"] == "requires_reauth"
    assert detail.json()["items"][0]["validation_code"] == "tdlib_artifact_verifier_not_enabled"
    assert "object_key" not in detail.text
    assert "tdlib/session" not in detail.text


def test_account_onboarding_expire_artifacts_marks_metadata_only(db_session) -> None:
    batch = AccountOnboardingBatch(
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        source_type="tdlib_directory",
        status="preview_ready",
        idempotency_key="artifact-expiry-batch",
        payload_hash="hash",
    )
    artifact = AccountOnboardingArtifact(
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        batch=batch,
        source_type="tdlib_directory",
        object_key="account-onboarding/workspace/artifact/private-key",
        sha256="0" * 64,
        size_bytes=10,
        content_type_detected="application/zip",
        status="validated",
        expires_at=utc_now() - timedelta(seconds=1),
    )
    db_session.add_all([batch, artifact])
    db_session.commit()

    expired = onboarding_service.expire_artifacts(db_session)

    assert expired == 1
    assert artifact.status == "expired"
    assert artifact.failure_code == "artifact_expired"
    events = db_session.query(AccountOnboardingEvent).filter_by(batch_id=batch.id).all()
    assert events
    assert "private-key" not in repr([event.safe_payload_json for event in events])


def test_account_onboarding_cleanup_deletes_expired_private_artifact_bytes(
    app_client, db_session
) -> None:
    uploaded = _upload_session_artifact(app_client, idempotency_key="cleanup-expired-upload")
    artifact = db_session.get(AccountOnboardingArtifact, uploaded["id"])
    assert artifact is not None
    path = onboarding_artifacts.private_artifact_path(artifact.object_key)
    assert path.exists()
    artifact.status = "expired"
    db_session.commit()

    deleted = onboarding_service.cleanup_artifact_files(db_session)

    assert deleted == 1
    assert not path.exists()
    assert artifact.status == "deleted"
    assert "object_key" not in repr(
        [event.safe_payload_json for event in db_session.query(AccountOnboardingEvent).all()]
    )


def test_account_onboarding_cleanup_keeps_validated_artifact_bytes(app_client, db_session) -> None:
    uploaded = _upload_session_artifact(app_client, idempotency_key="cleanup-validated-upload")
    artifact = db_session.get(AccountOnboardingArtifact, uploaded["id"])
    assert artifact is not None
    path = onboarding_artifacts.private_artifact_path(artifact.object_key)
    artifact.status = "validated"
    db_session.commit()

    deleted = onboarding_service.cleanup_artifact_files(db_session)

    assert deleted == 0
    assert path.exists()
    assert artifact.status == "validated"


def test_account_onboarding_cleanup_rejects_unsafe_object_key(db_session, tmp_path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("do-not-delete", encoding="utf-8")
    artifact = AccountOnboardingArtifact(
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        source_type="session_file",
        object_key="account-onboarding/../../outside.txt",
        sha256="0" * 64,
        size_bytes=10,
        content_type_detected="application/octet-stream",
        status="expired",
        expires_at=utc_now() - timedelta(seconds=1),
    )
    db_session.add(artifact)
    db_session.commit()

    deleted = onboarding_service.cleanup_artifact_files(db_session)

    assert deleted == 0
    assert outside.read_text(encoding="utf-8") == "do-not-delete"
    assert artifact.status == "expired"
    assert artifact.failure_code == "artifact_cleanup_unsafe_key"


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _post_account_onboarding_artifact(
    app_client,
    *,
    idempotency_key: str,
    content_base64: str,
    source_type: str = "tdlib_directory",
    filename: str = "tdlib.zip",
):
    return app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": idempotency_key,
            "source_type": source_type,
            "filename": filename,
            "content_base64": content_base64,
        },
    )


def _upload_session_artifact(app_client, *, idempotency_key: str) -> dict[str, object]:
    return app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": idempotency_key,
            "source_type": "session_file",
            "filename": "fixture.session.json",
            "content_base64": base64.b64encode(b'{"session":"fixture"}').decode("ascii"),
        },
    ).json()


def _artifact_row(
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    source_type: str,
    status: str = "quarantined",
) -> AccountOnboardingArtifact:
    return AccountOnboardingArtifact(
        id=new_id(),
        workspace_id=workspace_id,
        source_type=source_type,
        object_key="account-onboarding/test/artifact/private-key",
        sha256="0" * 64,
        size_bytes=10,
        content_type_detected="application/zip",
        status=status,
        expires_at=utc_now() + timedelta(days=1),
    )


def _create_waiting_auth_item(
    app_client,
    db_session,
    *,
    idempotency_key: str,
    status: str,
) -> tuple[str, str]:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": idempotency_key,
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    item_id = created["items"][0]["id"]
    item = db_session.get(AccountOnboardingItem, item_id)
    assert item is not None
    item.status = status
    db_session.commit()
    return created["batch"]["id"], item_id


def test_account_onboarding_submit_code_is_idempotent_and_redacted(app_client, db_session) -> None:
    batch_id, item_id = _create_waiting_auth_item(
        app_client,
        db_session,
        idempotency_key="onboarding-code-create",
        status="waiting_code",
    )

    body = {"idempotency_key": "onboarding-code-submit", "code": "12345"}
    first = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/code",
        json=body,
    )
    second = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/code",
        json=body,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "failed"
    assert first.json()["last_error_code"] == "auth_continuation_not_enabled"
    events = db_session.query(AccountOnboardingEvent).all()
    assert "12345" not in repr([event.safe_payload_json for event in events])


@pytest.mark.parametrize(
    ("status", "route", "field", "first_secret", "second_secret"),
    [
        ("waiting_code", "code", "code", "12345", "99999"),
        ("waiting_2fa", "password", "password", "first-secret", "second-secret"),
    ],
)
def test_account_onboarding_secret_idempotency_conflicts_on_different_payload(
    app_client, db_session, status, route, field, first_secret, second_secret
) -> None:
    batch_id, item_id = _create_waiting_auth_item(
        app_client,
        db_session,
        idempotency_key=f"onboarding-{route}-conflict-create",
        status=status,
    )

    path = f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/{route}"
    first = app_client.post(
        path,
        json={"idempotency_key": f"onboarding-{route}-conflict", field: first_secret},
    )
    assert first.status_code == 200
    assert first.json()["last_error_code"] == "auth_continuation_not_enabled"

    second = app_client.post(
        path,
        json={"idempotency_key": f"onboarding-{route}-conflict", field: second_secret},
    )

    assert second.status_code == 409
    assert second.json()["error_code"] == "ONBOARDING_INVALID_STATE"
    assert second_secret not in second.text


def test_account_onboarding_detail_is_workspace_scoped(app_client, db_session) -> None:
    foreign_workspace = Workspace(
        name="Foreign onboarding",
        slug="foreign-onboarding",
        owner_user_id=DEFAULT_LOCAL_USER_ID,
    )
    db_session.add(foreign_workspace)
    db_session.flush()
    batch = AccountOnboardingBatch(
        workspace_id=foreign_workspace.id,
        source_type="phone_bulk",
        status="preview_ready",
        label="Foreign",
        idempotency_key="foreign-onboarding-batch",
        payload_hash="hash",
    )
    db_session.add(batch)
    db_session.commit()

    response = app_client.get(f"/api/account-onboarding-batches/{batch.id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "ONBOARDING_BATCH_NOT_FOUND"
