from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS


def test_warmup_action_metadata_endpoint_returns_supported_actions(app_client) -> None:
    response = app_client.get("/api/warmup-actions/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == len(SUPPORTED_ADVANCED_ACTIONS)
    by_action = {item["action_type"]: item for item in payload}
    assert by_action["search_gif"] == {
        "action_type": "search_gif",
        "category": "entertainment",
        "traffic_heavy": True,
        "write_action": False,
        "requires_premium": False,
    }
    assert by_action["emoji_status"]["requires_premium"] is True
