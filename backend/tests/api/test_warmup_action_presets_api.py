from app.models import (
    AuditLog,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupStrategy,
    new_id,
)


def test_apply_warmup_strategy_preset_updates_limits_and_records_audit(app_client, db_session):
    strategy = _seed_strategy(db_session)
    strategy.daily_action_limits_json = {
        "1": {"feed_read": 4, "scroll_channels": 3, "saved_messages": 2}
    }
    db_session.commit()

    response = app_client.post(
        f"/api/warmup/strategies/{strategy.id}/apply-preset",
        json={"preset": "economic"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["daily_action_limits"]["1"]["feed_read"] == 4
    assert body["daily_action_limits"]["1"]["saved_messages"] == 2
    assert body["daily_action_limits"]["1"]["scroll_channels"] == 0
    audit = db_session.query(AuditLog).one()
    assert audit.action == "warmup_strategy_preset_applied"
    assert audit.entity_type == "warmup_strategy"
    assert audit.entity_id == strategy.id
    assert audit.metadata_json["preset"] == "economic"


def test_apply_warmup_strategy_preset_rejects_invalid_preset(app_client, db_session):
    strategy = _seed_strategy(db_session)

    response = app_client.post(
        f"/api/warmup/strategies/{strategy.id}/apply-preset",
        json={"preset": "turbo"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert db_session.query(AuditLog).count() == 0


def _seed_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Strategy {new_id()[:8]}",
        description="Action preset strategy",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=False,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy
