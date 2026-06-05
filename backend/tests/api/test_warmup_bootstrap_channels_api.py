from __future__ import annotations


def test_warmup_bootstrap_channel_admin_api_flow(app_client) -> None:
    created = app_client.post(
        "/api/warmup-bootstrap-channels",
        json={
            "channel_ref": "@bootstrap_api_flow",
            "category": "tech",
            "language": "en",
            "country": "US",
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["channel_ref"] == "@bootstrap_api_flow"
    assert payload["is_active"] is True

    listed = app_client.get(
        "/api/warmup-bootstrap-channels",
        params={"category": "tech", "language": "en"},
    )
    assert listed.status_code == 200
    assert [item["channel_ref"] for item in listed.json()] == ["@bootstrap_api_flow"]

    patched = app_client.patch(
        f"/api/warmup-bootstrap-channels/{payload['id']}",
        json={"is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False


def test_warmup_bootstrap_channel_rejects_private_invite_link(app_client) -> None:
    response = app_client.post(
        "/api/warmup-bootstrap-channels",
        json={
            "channel_ref": "https://t.me/+private",
            "category": "tech",
            "language": "en",
        },
    )

    assert response.status_code == 422
