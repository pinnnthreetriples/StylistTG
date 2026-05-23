from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from prometheus_client import CollectorRegistry, generate_latest

from app.main import app
from app.models import (
    AccountGgrScore,
    AccountProfileState,
    AccountProxy,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    Workspace,
    new_id,
    utc_now,
)
from app.observability.safety_metrics import SafetyMetrics
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from tests.helpers.factories import seed_account


def test_gate_blocked_increments_counter() -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=True)

    metrics.gate_blocked(workspace_id="workspace-1", intent="commenting", reason="ggr_too_low")

    assert (
        registry.get_sample_value(
            "safety_gate_blocks_total",
            {"workspace_id": "workspace-1", "intent": "commenting", "reason": "ggr_too_low"},
        )
        == 1.0
    )


def test_gate_evaluate_duration_context_records_histogram_count() -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=True)

    with metrics.gate_evaluate_duration(intent="commenting", cache_hit=False):
        pass

    assert (
        registry.get_sample_value(
            "safety_gate_evaluate_duration_seconds_count",
            {"intent": "commenting", "cache_hit": "false"},
        )
        == 1.0
    )


def test_cold_call_throttled_increments_counter() -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=True)

    metrics.cold_call_throttled(intent="commenting")

    assert (
        registry.get_sample_value(
            "safety_gate_cold_call_throttled_total",
            {"intent": "commenting"},
        )
        == 1.0
    )


def test_disabled_metrics_are_noop_with_empty_registry() -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=False)

    metrics.gate_blocked(workspace_id="workspace-1", intent="commenting", reason="ggr_too_low")
    with metrics.gate_evaluate_duration(intent="commenting", cache_hit=False):
        pass
    metrics.cold_call_throttled(intent="commenting")
    metrics.flood_wait(workspace_id="workspace-1", account_id="account-raw-id")

    payload = generate_latest(registry).decode("utf-8")
    assert "safety_gate_blocks_total" not in payload
    assert "account_total" not in payload
    assert "safety_gate_evaluate_duration_seconds" not in payload
    assert "safety_gate_cold_call_throttled_total" not in payload
    assert "flood_wait_total" not in payload


def test_metrics_endpoint_allows_internal_scrape_header(app_client, monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.metrics_enabled", True)
    monkeypatch.setattr("app.main.settings.metrics_allow_public", False)

    response = app_client.get("/metrics", headers={"X-Internal-Scrape": "true"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")


def test_metrics_endpoint_rejects_public_scrape_without_header(app_client, monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.metrics_enabled", True)
    monkeypatch.setattr("app.main.settings.metrics_allow_public", False)

    response = app_client.get("/metrics")

    assert response.status_code == 403
    assert response.json()["detail"] == "metrics scrape requires internal authorization"


def test_metrics_endpoint_is_not_in_openapi_schema() -> None:
    app.openapi_schema = None
    schema = app.openapi()

    assert "/metrics" not in schema["paths"]


def test_gate_evaluate_blocked_verdict_increments_block_counter(db_session) -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=True)
    account = _ready_account(db_session)
    _make_ggr(db_session, account, score=3.5)
    db_session.commit()

    gate = AccountSafetyGate(cache=InMemorySafetyGateCache(), metrics=metrics)
    verdict = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.severity == "blocked"
    assert (
        registry.get_sample_value(
            "safety_gate_blocks_total",
            {
                "workspace_id": account.workspace_id,
                "intent": "commenting",
                "reason": "ggr_too_low",
            },
        )
        == 1.0
    )


def test_flood_wait_uses_short_account_hash_label_only() -> None:
    registry = CollectorRegistry()
    metrics = SafetyMetrics(registry=registry, enabled=True)
    raw_account_id = "account-raw-id"
    expected_hash = hashlib.sha256(raw_account_id.encode("utf-8")).hexdigest()[:8]

    metrics.flood_wait(workspace_id="workspace-1", account_id=raw_account_id)

    payload = generate_latest(registry).decode("utf-8")
    assert raw_account_id not in payload
    assert f'account_id_hash="{expected_hash}"' in payload


def test_alert_rules_yaml_is_valid_and_has_required_alerts() -> None:
    runbook = Path("../docs/runbooks/safety-alerts.md")
    text = runbook.read_text(encoding="utf-8")
    yaml_block = text.split("```yaml", 1)[1].split("```", 1)[0]

    parsed = yaml.safe_load(yaml_block)
    alerts = {
        rule["alert"] for group in parsed["groups"] for rule in group["rules"] if "alert" in rule
    }

    assert {
        "QuarantineEpidemic",
        "GgrWeakBucketGrowth",
        "GateBlockBurst",
        "SendDurationSlow",
    } <= alerts


def _ready_account(
    db_session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
):
    account = seed_account(
        db_session,
        external_ref="+15550103000",
        workspace_id=workspace_id,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = utc_now()
    policy_workspace = db_session.get(Workspace, workspace_id)
    policy_workspace.safety_pipeline_v2_enabled = True
    db_session.add(
        AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            host="127.0.0.1",
            port=1080,
            status="tdlib_working",
        )
    )
    db_session.add(
        AccountProfileState(
            account_id=account.id,
            first_name="Anna",
            bio="Long enough profile bio",
            username="anna",
            profile_photo_asset_id="00000000-0000-4000-8000-000000000201",
        )
    )
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=account.workspace_id,
        name=f"strategy-{new_id()}",
        tier_limits_json={},
        target_channels_json=[],
        duration_days=14,
    )
    db_session.add(strategy)
    db_session.flush()
    db_session.add(
        WarmupSession(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            strategy_id=strategy.id,
            status=WarmupStatus.COMPLETED.value,
            current_day=3,
            duration_days=14,
            completed_at=utc_now(),
        )
    )
    _make_ggr(db_session, account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _make_ggr(db_session, account, *, score: float = 8.0) -> None:
    db_session.query(AccountGgrScore).filter(AccountGgrScore.account_id == account.id).delete()
    db_session.add(
        AccountGgrScore(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            score=score,
            bucket="strong" if score >= 7 else "weak" if score < 4 else "medium",
            breakdown_json={"fraud_score": 0.1},
            last_calculated_at=utc_now(),
            next_calculation_at=utc_now(),
        )
    )
