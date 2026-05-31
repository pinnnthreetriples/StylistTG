# Performance Benchmarks Runbook

StylistTG keeps a small performance budget suite for hot service paths where
slowdowns directly affect sender throughput. Task 27 covers `AccountSafetyGate`.

## AccountSafetyGate SLOs

| Case | Budget |
| --- | --- |
| `evaluate()` cache hit | p95 < 50 ms |
| `evaluate()` cold cache miss | p95 < 200 ms |
| `reserve()` Lua path | p95 < 5 ms |
| Cold evaluate calls | <= 1 per account and intent per minute |

Benchmarks live in `backend/tests/benchmarks/test_safety_gate_perf.py`.
They are marked `benchmark` and `slow`, and normal pytest runs disable timing
with `--benchmark-disable`.

No live TDLib, Telegram, secrets, or real account runtime data are required.
Benchmark fixtures seed local test data only.

Nightly CI first runs the same benchmark tests once with
`--benchmark-disable -q` as a smoke check, then runs the benchmark-only
performance gate.

## CI Baseline Policy

Nightly CI does not compare the GitHub-hosted runner output against the checked-in
`pytest-benchmark` baseline file. Those saved baseline files include
machine/Python/OS metadata, so comparing a Linux/Python runner with a local
Windows baseline can fail before product performance is evaluated.

CI writes a fresh benchmark JSON on the current runner and enforces the absolute
SLOs above with `tools/check_benchmark_budget.py`. Local/developer baseline
comparison remains useful for manual triage when the baseline was produced on the
same runner family and Python version.

## Local Run

From `backend/`:

```powershell
uv run --extra test pytest tests/benchmarks/ `
  --benchmark-enable `
  --benchmark-only `
  --benchmark-storage=file://./benchmark_storage `
  --benchmark-compare=tests/benchmarks/baselines/safety_gate_baseline.json `
  --benchmark-compare-fail=mean:20%
```

For a quick import/smoke check without perf enforcement:

```powershell
uv run --extra test pytest tests/benchmarks/ --benchmark-disable -q
```

## Reading Output

`pytest-benchmark` reports `min`, `max`, `mean`, `stddev`, `median`, `iqr`,
outliers, rounds, and iterations. Use `median`/`iqr` to judge noise, `mean` for
the committed regression gate, and p95/p99 from the saved JSON when writing PR
notes.

The nightly gate writes `backend/reports/safety_gate_benchmark.json` on the
current GitHub runner and fails only when `tools/check_benchmark_budget.py`
detects an absolute SLO violation. This avoids `pytest-benchmark`
`machine_info` mismatches while still making failures actionable. The workflow
comments on an existing open benchmark issue with the same title/label instead
of opening duplicates for the same root cause.

## Regression Triage

1. Re-run locally with `--benchmark-enable` and confirm the regression repeats.
2. Inspect recent changes on the hot path: cache key creation, DB queries,
   Redis calls, GGR/profile completeness, warmup lookups, and reserve Lua calls.
3. Profile the slow case if repeated: start with the benchmark output, then add
   focused instrumentation or `--benchmark-cprofile=tottime`.
4. Fix or revert the regression. Do not update the baseline to hide accidental
   slowdowns.

## Updating Baseline

Update baseline only after an intentional optimization or accepted architecture
change. Use a separate PR with the reason in the commit message and PR body.

From `backend/`:

```powershell
uv run --extra test pytest tests/benchmarks/test_safety_gate_perf.py `
  --benchmark-enable `
  --benchmark-save=baseline `
  --benchmark-save-data `
  --benchmark-storage=file://./benchmark_storage

Copy-Item -Force `
  benchmark_storage/<platform>/0001_baseline.json `
  tests/benchmarks/baselines/safety_gate_baseline.json
```

After copying, run the compare command once to confirm the baseline file is
readable by `pytest-benchmark`.
