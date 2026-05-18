from __future__ import annotations


def test_account_create_returns_rfc3339_datetimes(app_client) -> None:
    response = app_client.post(
        "/api/accounts",
        json={"external_ref": "+15550102000", "telegram_user_id": "123456"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created_at"].endswith("Z") or "+" in body["created_at"]
    assert body["updated_at"].endswith("Z") or "+" in body["updated_at"]


def test_account_create_rejects_empty_external_ref(app_client) -> None:
    response = app_client.post("/api/accounts", json={"external_ref": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "external_ref" for error in body["field_errors"])


def test_account_create_duplicate_external_ref_returns_conflict(app_client) -> None:
    payload = {"external_ref": "+15550102001"}

    first = app_client.post("/api/accounts", json=payload)
    second = app_client.post("/api/accounts", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error_code"] == "ACCOUNT_ALREADY_EXISTS"
