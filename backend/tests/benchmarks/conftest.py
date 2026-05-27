from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.models import DEFAULT_LOCAL_WORKSPACE_ID
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from tests.test_account_safety_gate import _ready_account


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
    account = _ready_account(db_session, external_ref="+15550990001")
    gate_service.evaluate(account.id, intent="commenting")
    return account.id


@pytest.fixture()
def cold_account(db_session) -> str:
    account = _ready_account(db_session, external_ref="+15550990002")
    return account.id


@pytest.fixture()
def rate_keys() -> dict[str, Any]:
    return {"redis": _LuaReserveRedis(), "max_concurrent": 100_000}


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

    def eval(self, _script, _numkeys, _zset_key, _now, _ttl, max_concurrent, *_args):
        if self.current_count >= int(max_concurrent):
            return [0, self.current_count]
        self.current_count += 1
        return [1, self.current_count]
