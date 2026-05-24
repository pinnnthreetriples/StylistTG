from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast


BUDGETS_SECONDS = {
    "account_safety_gate.evaluate.cache_hit": 0.050,
    "account_safety_gate.evaluate.cold": 0.200,
    "account_safety_gate.reserve.lua": 0.005,
}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate percentile for an empty sample")
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


JsonObject = dict[str, object]
JsonList = list[object]


def _as_object(value: object) -> JsonObject | None:
    if isinstance(value, dict):
        return cast(JsonObject, value)
    return None


def _as_list(value: object) -> JsonList | None:
    if isinstance(value, list):
        return cast(JsonList, value)
    return None


def _benchmark_group(benchmark: JsonObject) -> str:
    group = benchmark.get("group")
    if isinstance(group, str) and group:
        return group
    options = _as_object(benchmark.get("options"))
    if options is not None:
        group = options.get("group")
        if isinstance(group, str) and group:
            return group
    fullname = str(benchmark.get("fullname", ""))
    for candidate in BUDGETS_SECONDS:
        if candidate in fullname:
            return candidate
    return ""


def check_budget(report_path: Path) -> list[str]:
    report = _as_object(json.loads(report_path.read_text(encoding="utf-8")))
    if report is None:
        return ["benchmark JSON root is not an object"]
    benchmarks = _as_list(report.get("benchmarks"))
    if benchmarks is None:
        return ["benchmark JSON does not contain a benchmark list"]

    seen: set[str] = set()
    failures: list[str] = []
    for raw_benchmark in benchmarks:
        benchmark = _as_object(raw_benchmark)
        if benchmark is None:
            continue
        group = _benchmark_group(benchmark)
        if group not in BUDGETS_SECONDS:
            continue
        seen.add(group)
        stats = _as_object(benchmark.get("stats"))
        data = stats.get("data") if stats is not None else None
        samples_data = _as_list(data)
        if not samples_data:
            failures.append(f"{group}: missing sample data")
            continue
        samples: list[float] = []
        for value in samples_data:
            if not isinstance(value, int | float):
                failures.append(f"{group}: sample data contains a non-numeric value")
                break
            samples.append(float(value))
        if len(samples) != len(samples_data):
            continue
        p95 = _percentile(samples, 0.95)
        maximum = max(samples)
        budget = BUDGETS_SECONDS[group]
        if p95 > budget:
            failures.append(
                f"{group}: p95={p95 * 1000:.3f}ms exceeds budget "
                f"{budget * 1000:.3f}ms (max={maximum * 1000:.3f}ms)"
            )
        else:
            print(
                f"{group}: p95={p95 * 1000:.3f}ms "
                f"<= {budget * 1000:.3f}ms (max={maximum * 1000:.3f}ms)"
            )

    missing = sorted(set(BUDGETS_SECONDS) - seen)
    failures.extend(f"{group}: benchmark group missing from report" for group in missing)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate pytest-benchmark JSON against absolute SLO budgets."
    )
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    failures = check_budget(args.report)
    if failures:
        print("BENCHMARK_BUDGET_EXCEEDED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
