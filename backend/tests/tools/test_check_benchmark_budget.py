from __future__ import annotations

import json

from tools.check_benchmark_budget import check_budget


def _report(*benchmarks: dict) -> dict:
    return {"benchmarks": list(benchmarks)}


def _benchmark(group: str, samples: list[float]) -> dict:
    return {
        "group": group,
        "fullname": f"tests/benchmarks/test_safety_gate_perf.py::{group}",
        "stats": {"data": samples},
    }


def test_budget_passes_for_all_safety_gate_groups(tmp_path) -> None:
    report = tmp_path / "benchmark.json"
    report.write_text(
        json.dumps(
            _report(
                _benchmark("account_safety_gate.evaluate.cache_hit", [0.001, 0.002]),
                _benchmark("account_safety_gate.evaluate.cold", [0.010, 0.020]),
                _benchmark("account_safety_gate.reserve.lua", [0.0005, 0.001]),
            )
        ),
        encoding="utf-8",
    )

    assert check_budget(report) == []


def test_budget_reports_slo_failures_without_machine_info(tmp_path) -> None:
    report = tmp_path / "benchmark.json"
    report.write_text(
        json.dumps(
            _report(
                _benchmark("account_safety_gate.evaluate.cache_hit", [0.001, 0.060]),
                _benchmark("account_safety_gate.evaluate.cold", [0.010, 0.020]),
                _benchmark("account_safety_gate.reserve.lua", [0.0005, 0.001]),
            )
        ),
        encoding="utf-8",
    )

    failures = check_budget(report)

    assert failures == [
        "account_safety_gate.evaluate.cache_hit: p95=57.050ms exceeds budget "
        "50.000ms (max=60.000ms)"
    ]


def test_budget_reports_missing_groups(tmp_path) -> None:
    report = tmp_path / "benchmark.json"
    report.write_text(
        json.dumps(_report(_benchmark("account_safety_gate.evaluate.cache_hit", [0.001]))),
        encoding="utf-8",
    )

    failures = check_budget(report)

    assert failures == [
        "account_safety_gate.evaluate.cold: benchmark group missing from report",
        "account_safety_gate.reserve.lua: benchmark group missing from report",
    ]
