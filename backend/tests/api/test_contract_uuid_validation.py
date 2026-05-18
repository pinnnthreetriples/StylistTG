from __future__ import annotations


def test_account_update_preview_rejects_empty_account_id(app_client) -> None:
    response = app_client.post(
        "/api/account-update/preview",
        json={
            "account_id": "",
            "stories": [{"action": "post_image", "asset_id": "", "protect_content": 0}],
        },
    )

    assert response.status_code == 422
    assert "sqlalchemy" not in response.text.lower()


def test_warmup_validate_rejects_empty_account_id(app_client) -> None:
    response = app_client.post(
        "/api/warmup/validate",
        json={"account_id": "", "strategy_id": ""},
    )

    assert response.status_code == 422
    assert "sqlalchemy" not in response.text.lower()


def test_warmup_session_path_rejects_non_uuid(app_client) -> None:
    response = app_client.get("/api/warmup/sessions/0")

    assert response.status_code == 422
    assert "sqlalchemy" not in response.text.lower()
