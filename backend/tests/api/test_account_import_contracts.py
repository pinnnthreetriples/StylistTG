from __future__ import annotations


def test_account_import_create_rejects_string_dry_run(app_client) -> None:
    response = app_client.post(
        "/api/account-import-batches",
        json={"source_type": "tdata", "dry_run": "false"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "dry_run" for error in body["field_errors"])
    assert any(
        error["loc"][-1] == "dry_run" and error["type"] == "bool_type"
        for error in body["details"]["errors"]
    )


def test_account_import_detail_rejects_non_uuid_batch_id(app_client) -> None:
    response = app_client.get("/api/account-import-batches/not-a-uuid")

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "path.batch_id" for error in body["field_errors"])
    assert any(
        error["loc"][-1] == "batch_id" and error["type"] == "uuid_parsing"
        for error in body["details"]["errors"]
    )


def test_account_import_create_returns_rfc3339_datetimes(app_client) -> None:
    response = app_client.post(
        "/api/account-import-batches",
        json={"source_type": "tdata", "metadata": {}},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created_at"].endswith("Z") or "+" in body["created_at"]


def test_account_import_validate_rejects_invalid_base64_at_schema_boundary(app_client) -> None:
    response = app_client.post(
        "/api/account-import-batches/00000000-0000-4000-8000-000000000001/validate",
        json={"content_base64": "***"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "content_base64" for error in body["field_errors"])
