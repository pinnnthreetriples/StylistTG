from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest

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
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from app.services.workspace_safety_policy import get_workspace_safety_policy
from tests.helpers.factories import seed_account


@dataclass
class BenchmarkGateService:
    session: Any
    gate: AccountSafetyGate

    def evaluate(self, account_id: str, *, intent: str):
        return self.gate.evaluate(
            self.session,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account_id,
            intent=intent,
        )

    def reset_gate(self) -> None:
        self.gate = AccountSafetyGate(cache=InMemorySafetyGateCache(), redis_client=_BudgetRedis())

    def reserve(self, account_id: str, *, intent: str, rate_limit_keys: dict[str, int]):
        from app.services.safety_gate_reserve import reserve

        return reserve(
            rate_limit_keys["redis"],
            account_id=account_id,
            intent=intent,
            max_concurrent=rate_limit_keys["max_concurrent"],
        )


@pytest.fixture()
def gate_service(db_session) -> BenchmarkGateService:
    return BenchmarkGateService(
        session=db_session,
        gate=AccountSafetyGate(cache=InMemorySafetyGateCache(), redis_client=_BudgetRedis()),
    )


@pytest.fixture()
def warmed_account(db_session, gate_service: BenchmarkGateService) -> str:
    account = _ready_benchmark_account(db_session, external_ref="+15550990001")
    gate_service.evaluate(account.id, intent="commenting")
    return account.id


@pytest.fixture()
def cold_account(db_session) -> str:
    account = _ready_benchmark_account(db_session, external_ref="+15550990002")
    return account.id


@pytest.fixture()
def rate_keys() -> dict[str, Any]:
    return {"redis": _LuaReserveRedis(), "max_concurrent": 100_000}


def _ready_benchmark_account(db_session, *, external_ref: str):
    account = seed_account(
        db_session,
        external_ref=external_ref,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = utc_now() - timedelta(days=30)
    account.pinned_channel_ref = "@bench_channel"
    policy = get_workspace_safety_policy(
        db_session, workspace_id=account.workspace_id, create_if_missing=True
    )
    policy.min_account_age_hours = 24
    policy.min_warmup_days = 3
    policy.require_healthy_proxy = True
    policy.require_warmup_before_commenting = True
    policy.auto_pause_on_flood_wait_count = 3
    workspace = db_session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
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
            first_name="Bench",
            bio="Benchmark-ready profile bio",
            username=f"bench_{account.id[:8]}",
            profile_photo_asset_id="00000000-0000-4000-8000-000000000301",
        )
    )
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=account.workspace_id,
        name=f"benchmark-strategy-{new_id()}",
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
    db_session.add(
        AccountGgrScore(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            score=8.0,
            bucket="strong",
            breakdown_json={"fraud_score": 0.1},
            last_calculated_at=utc_now(),
            next_calculation_at=utc_now() + timedelta(hours=6),
        )
    )
    db_session.commit()
    db_session.refresh(account)
    return account


class _BudgetRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        _ = (key, seconds)


class _LuaReserveRedis:
    def __init__(self) -> None:
        self.current_count = 0

    def eval(self, _script, _numkeys, _counter_key, _reservation_key, max_concurrent, *_args):
        if self.current_count >= int(max_concurrent):
            return [0, self.current_count]
        self.current_count += 1
        return [1, self.current_count]
