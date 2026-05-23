from __future__ import annotations

from datetime import timedelta

import pytest

from app.contracts.safety_gate import SafetyGateReason, SafetyGateVerdict
from app.main import app
from app.models import (
    AccountGgrScore,
    AccountOperationCooldown,
    AccountProfileState,
    AccountProxy,
    AccountQuarantine,
    AccountState,
    AccountStatusObservation,
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    CrossModuleLoadBucket,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    Workspace,
    new_id,
    utc_now,
)
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.workspace_safety_policy import get_workspace_safety_policy
from tests.helpers.factories import seed_account, seed_two_workspaces


def _auth(workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role="viewer",
        auth_source="test",
    )


@pytest.fixture()
def viewer_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth()
    return app_client


@pytest.mark.parametrize(
    ("setup_name", "expected_code"),
    [
        ("proxy_unhealthy", "proxy_unhealthy"),
        ("no_warmup", "no_warmup"),
        ("warmup_incomplete", "warmup_incomplete"),
        ("age_too_low", "age_too_low"),
        ("flood_wait_streak", "flood_wait_streak"),
        ("fraud_score_high", "fraud_score_high"),
        ("ggr_too_low", "ggr_too_low"),
        ("status_degraded", "status_degraded"),
        ("profile_incomplete", "profile_incomplete"),
        ("active_quarantine", "active_quarantine"),
        ("cross_module_overload", "cross_module_overload"),
        ("terminal_status", "terminal_status"),
        ("ip_change_cooldown", "ip_change_cooldown"),
    ],
)
def test_commenting_reason_code_triggers(db_session, setup_name, expected_code) -> None:
    account = _ready_account(db_session)
    _REASON_SETUPS[setup_name](db_session, account)

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert expected_code in {reason.code for reason in verdict.reasons}


@pytest.mark.parametrize("intent", ["editing", "warmup", "commenting"])
def test_happy_path_intents_are_ok(db_session, intent) -> None:
    account = _ready_account(db_session)

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent=intent,
    )

    assert {
        "eligible": verdict.eligible,
        "severity": verdict.severity,
        "reasons": verdict.reasons,
    } == {
        "eligible": True,
        "severity": "ok",
        "reasons": [],
    }


@pytest.mark.parametrize("intent", ["editing", "warmup", "commenting"])
@pytest.mark.parametrize("terminal_status", ["banned", "deleted", "suspended"])
def test_terminal_status_blocks_all_intents(db_session, intent, terminal_status) -> None:
    account = _ready_account(db_session)
    account.terminal_status = terminal_status
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent=intent,
    )

    reason = next(reason for reason in verdict.reasons if reason.code == "terminal_status")
    assert {
        "eligible": verdict.eligible,
        "severity": verdict.severity,
        "reason_severity": reason.severity,
        "metadata": reason.metadata,
    } == {
        "eligible": False,
        "severity": "blocked",
        "reason_severity": "blocked",
        "metadata": {"status": terminal_status},
    }


def test_cache_miss_writes_verdict(db_session) -> None:
    account = _ready_account(db_session)
    cache = InMemorySafetyGateCache()

    verdict = AccountSafetyGate(cache=cache).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert cache.size == 1
    assert verdict.cache_ttl_seconds == 60


def test_cache_hit_uses_cached_verdict_without_recompute(db_session) -> None:
    account = _ready_account(db_session)
    cache = InMemorySafetyGateCache()
    gate = AccountSafetyGate(cache=cache)
    first = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    account.account_state = AccountState.DISABLED
    db_session.commit()
    second = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert second == first


def test_terminal_status_change_invalidates_cached_allow_verdict(db_session) -> None:
    account = _ready_account(db_session)
    cache = InMemorySafetyGateCache()
    gate = AccountSafetyGate(cache=cache)
    gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    account.terminal_status = "banned"
    db_session.commit()
    second = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    reason = next(reason for reason in second.reasons if reason.code == "terminal_status")
    assert {
        "eligible": second.eligible,
        "severity": second.severity,
        "reason_metadata": reason.metadata,
        "cache_size": cache.size,
    } == {
        "eligible": False,
        "severity": "blocked",
        "reason_metadata": {"status": "banned"},
        "cache_size": 2,
    }


def test_policy_updated_at_changes_cache_key(db_session) -> None:
    account = _ready_account(db_session)
    cache = InMemorySafetyGateCache()
    gate = AccountSafetyGate(cache=cache)
    gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )
    policy = get_workspace_safety_policy(
        db_session, workspace_id=account.workspace_id, create_if_missing=True
    )
    policy.updated_at = utc_now() + timedelta(minutes=1)
    db_session.commit()

    gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert cache.size == 2


def test_cold_call_first_cache_miss_computes_and_tracks_budget(db_session) -> None:
    account = _ready_account(db_session)
    redis = _FakeColdCallRedis()
    cache = InMemorySafetyGateCache()

    verdict = AccountSafetyGate(cache=cache, redis_client=redis).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.severity == "ok"
    assert redis.values[f"gate:cold:{account.id}:commenting"] == 1
    assert redis.expirations[f"gate:cold:{account.id}:commenting"] == 60
    assert cache.size == 2


def test_cold_call_budget_exceeded_returns_stale_verdict(db_session) -> None:
    account = _ready_account(db_session)
    redis = _FakeColdCallRedis()
    cache = InMemorySafetyGateCache()
    gate = AccountSafetyGate(cache=cache, redis_client=redis)
    first = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )
    policy = get_workspace_safety_policy(
        db_session, workspace_id=account.workspace_id, create_if_missing=True
    )
    policy.updated_at = utc_now() + timedelta(minutes=1)
    db_session.commit()

    second = gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert second == first
    assert redis.values[f"gate:cold:{account.id}:commenting"] == 2


def test_cache_hit_does_not_increment_cold_call_budget(db_session) -> None:
    account = _ready_account(db_session)
    redis = _FakeColdCallRedis()
    cache = InMemorySafetyGateCache()
    gate = AccountSafetyGate(cache=cache, redis_client=redis)

    gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )
    gate.evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert redis.values[f"gate:cold:{account.id}:commenting"] == 1


def test_cold_call_budget_exceeded_without_stale_fails_closed(db_session) -> None:
    account = _ready_account(db_session)
    redis = _FakeColdCallRedis(values={f"gate:cold:{account.id}:commenting": 1})

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache(), redis_client=redis).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is False
    assert verdict.severity == "blocked"
    assert verdict.reasons[0].metadata["budget"] == "cold_call"


def test_cold_call_throttle_logs_metric_event(db_session, monkeypatch) -> None:
    account = _ready_account(db_session)
    redis = _FakeColdCallRedis(values={f"gate:cold:{account.id}:commenting": 1})
    events: list[dict[str, str]] = []

    def _capture(event: str, **fields: str) -> None:
        events.append({"event": event, **fields})

    monkeypatch.setattr("app.services.account_safety_gate.log_event", _capture)

    AccountSafetyGate(cache=InMemorySafetyGateCache(), redis_client=redis).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert events == [
        {
            "event": "safety_gate_cold_call_throttled_total",
            "intent": "commenting",
        }
    ]


def test_api_tenant_isolation_returns_404(viewer_client, db_session) -> None:
    _workspace_a, workspace_b = seed_two_workspaces(db_session)
    account = _ready_account(db_session, workspace_id=workspace_b, external_ref="+15550109901")

    response = viewer_client.get(f"/api/accounts/{account.id}/safety-gate?intent=commenting")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_multi_reason_aggregation_blocks_with_warning_present(db_session) -> None:
    account = _ready_account(db_session)
    _make_ggr(db_session, account, score=3.5, fraud_score=0.9)
    _make_ip_cooldown(db_session, account)

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert {"eligible": verdict.eligible, "severity": verdict.severity} == {
        "eligible": False,
        "severity": "blocked",
    }
    assert {"ggr_too_low", "fraud_score_high", "ip_change_cooldown"} <= {
        reason.code for reason in verdict.reasons
    }


def test_safety_gate_contract_round_trips_json() -> None:
    verdict = SafetyGateVerdict(
        account_id="00000000-0000-4000-8000-000000000001",
        intent="editing",
        eligible=True,
        severity="warning",
        reasons=[
            SafetyGateReason(
                code="proxy_unhealthy",
                severity="warning",
                message="Proxy is not healthy",
                metadata={"status": "failed"},
            )
        ],
        ggr_score=5.0,
        checked_at=utc_now(),
        cache_ttl_seconds=60,
    )

    assert SafetyGateVerdict.model_validate_json(verdict.model_dump_json()) == verdict


def _ready_account(
    db_session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    external_ref: str = "+15550103000",
):
    account = seed_account(
        db_session,
        external_ref=external_ref,
        workspace_id=workspace_id,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = utc_now() - timedelta(days=30)
    account.pinned_channel_ref = "@channel"
    policy = get_workspace_safety_policy(
        db_session, workspace_id=workspace_id, create_if_missing=True
    )
    policy.min_account_age_hours = 24
    policy.min_warmup_days = 3
    policy.require_healthy_proxy = True
    policy.require_warmup_before_commenting = True
    policy.auto_pause_on_flood_wait_count = 3
    workspace = db_session.get(Workspace, workspace_id)
    workspace.safety_pipeline_v2_enabled = True
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
    _make_warmup(db_session, account, status=WarmupStatus.COMPLETED.value, current_day=3)
    _make_ggr(db_session, account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _make_warmup(db_session, account, *, status: str, current_day: int) -> None:
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
            status=status,
            current_day=current_day,
            duration_days=14,
            completed_at=utc_now() if status == WarmupStatus.COMPLETED.value else None,
        )
    )


def _make_ggr(db_session, account, *, score: float = 8.0, fraud_score: float = 0.1) -> None:
    db_session.query(AccountGgrScore).filter(AccountGgrScore.account_id == account.id).delete()
    db_session.add(
        AccountGgrScore(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            score=score,
            bucket="strong" if score >= 7 else "weak" if score < 4 else "medium",
            breakdown_json={"fraud_score": fraud_score},
            last_calculated_at=utc_now(),
            next_calculation_at=utc_now() + timedelta(hours=6),
        )
    )


def _make_ip_cooldown(db_session, account) -> None:
    db_session.add(
        AccountStatusObservation(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            observed_at=utc_now(),
            proxy_healthy=True,
            tdlib_authorized=True,
            consecutive_failures=0,
            auto_action_taken="cooldown",
            details_json={"reason": "ip_change_detected"},
        )
    )
    db_session.flush()


def _setup_proxy_unhealthy(db_session, account) -> None:
    account.proxy.status = "failed"
    db_session.commit()


def _setup_no_warmup(db_session, account) -> None:
    db_session.query(WarmupSession).filter(WarmupSession.account_id == account.id).delete()
    db_session.commit()


def _setup_warmup_incomplete(db_session, account) -> None:
    db_session.query(WarmupSession).filter(WarmupSession.account_id == account.id).delete()
    _make_warmup(db_session, account, status=WarmupStatus.ACTIVE.value, current_day=1)
    db_session.commit()


def _setup_age_too_low(db_session, account) -> None:
    account.created_at = utc_now()
    db_session.commit()


def _setup_flood_wait_streak(db_session, account) -> None:
    for index in range(3):
        db_session.add(
            AccountOperationCooldown(
                account_id=account.id,
                operation="commenting",
                level="blocked",
                reason_code="recent_flood_wait",
                started_at=utc_now() - timedelta(hours=index),
                retry_after_at=utc_now() + timedelta(hours=1),
                source="test",
            )
        )
    db_session.commit()


def _setup_fraud_score_high(db_session, account) -> None:
    _make_ggr(db_session, account, score=8.0, fraud_score=0.9)
    db_session.commit()


def _setup_ggr_too_low(db_session, account) -> None:
    _make_ggr(db_session, account, score=3.5)
    db_session.commit()


def _setup_status_degraded(db_session, account) -> None:
    db_session.add(
        AccountStatusObservation(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            observed_at=utc_now(),
            proxy_healthy=False,
            tdlib_authorized=True,
            consecutive_failures=3,
            auto_action_taken="paused",
            details_json={"reason": "degraded"},
        )
    )
    db_session.commit()


def _setup_profile_incomplete(db_session, account) -> None:
    account.profile_state.bio = ""
    account.profile_state.profile_photo_asset_id = None
    db_session.commit()


def _setup_active_quarantine(db_session, account) -> None:
    db_session.add(
        AccountQuarantine(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            reason="manual",
            started_at=utc_now(),
            until=utc_now() + timedelta(hours=24),
            metadata_json={},
        )
    )
    db_session.commit()


def _setup_cross_module_overload(db_session, account) -> None:
    db_session.add(
        CrossModuleLoadBucket(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            bucket_start=utc_now().replace(minute=0, second=0, microsecond=0),
            commenting_actions=25,
        )
    )
    db_session.commit()


def _setup_terminal_status(db_session, account) -> None:
    account.terminal_status = "banned"
    db_session.commit()


def _setup_ip_change_cooldown(db_session, account) -> None:
    _make_ip_cooldown(db_session, account)
    db_session.commit()


_REASON_SETUPS = {
    "proxy_unhealthy": _setup_proxy_unhealthy,
    "no_warmup": _setup_no_warmup,
    "warmup_incomplete": _setup_warmup_incomplete,
    "age_too_low": _setup_age_too_low,
    "flood_wait_streak": _setup_flood_wait_streak,
    "fraud_score_high": _setup_fraud_score_high,
    "ggr_too_low": _setup_ggr_too_low,
    "status_degraded": _setup_status_degraded,
    "profile_incomplete": _setup_profile_incomplete,
    "active_quarantine": _setup_active_quarantine,
    "cross_module_overload": _setup_cross_module_overload,
    "terminal_status": _setup_terminal_status,
    "ip_change_cooldown": _setup_ip_change_cooldown,
}


class _FakeColdCallRedis:
    def __init__(self, *, values: dict[str, int] | None = None) -> None:
        self.values = dict(values or {})
        self.expirations: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds
