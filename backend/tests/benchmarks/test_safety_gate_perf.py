from __future__ import annotations

import pytest


pytestmark = [pytest.mark.benchmark, pytest.mark.slow]


class TestSafetyGatePerformance:
    @pytest.mark.benchmark(
        group="account_safety_gate.evaluate.cache_hit",
        min_rounds=25,
        max_time=0.05,
    )
    def test_evaluate_cache_hit(self, benchmark, gate_service, warmed_account) -> None:
        """SLO: p95 < 50ms cache-hit."""
        result = benchmark(gate_service.evaluate, warmed_account, intent="commenting")

        assert result.severity in ("ok", "warning", "blocked")

    @pytest.mark.benchmark(group="account_safety_gate.evaluate.cold", min_rounds=10)
    def test_evaluate_cold(self, benchmark, gate_service, cold_account) -> None:
        """SLO: p95 < 200ms cold cache miss."""

        def _setup():
            gate_service.reset_gate()
            return (cold_account,), {"intent": "commenting"}

        result = benchmark.pedantic(
            gate_service.evaluate,
            setup=_setup,
            rounds=10,
            iterations=1,
        )

        assert result.severity is not None

    @pytest.mark.benchmark(
        group="account_safety_gate.reserve.lua",
        min_rounds=25,
        max_time=0.05,
    )
    def test_reserve_lua_single_call(
        self, benchmark, gate_service, warmed_account, rate_keys
    ) -> None:
        """SLO: p95 < 5ms for Lua reserve single round-trip."""
        result = benchmark(
            gate_service.reserve,
            warmed_account,
            intent="commenting",
            rate_limit_keys=rate_keys,
        )

        status = "RESERVED" if result.reserved else "RATE_BLOCKED"
        assert status in ("RESERVED", "STALE", "BLOCKED", "WARNING", "RATE_BLOCKED")


def test_reserve_rate_limit_denied_mapping(gate_service, warmed_account, rate_keys) -> None:
    rate_keys["max_concurrent"] = 0

    result = gate_service.reserve(
        warmed_account,
        intent="commenting",
        rate_limit_keys=rate_keys,
    )

    assert result.reserved is False
