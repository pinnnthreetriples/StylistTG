# Sub-agent C: Resilience Findings

Task: GitHub issue #148, Task 42 full safety pipeline audit.

Scope: dimensions 5 failure modes, 13 performance/SLO, and 14 observability. This was a static/targeted audit only. No live TDLib, Telegram, production DB, production Redis, dependency installs, migrations, or production-like operations were run.

## Summary

- Findings: 6 total.
- Severity: P1 = 2, P2 = 3, P3 = 1.
- Dimensions covered: failure modes, performance/SLO, observability.
- Primary risks: Redis-down fail-open behavior for send concurrency, broken quarantine ratio dashboard query, stale denominator metrics, weak-GGR alert math, Redis-outage DB stampede risk, and DB pool observability gaps.

## Findings

### F-301 Redis-down gate reserve fails open for live send concurrency

Severity: P1

Dimension: 5 failure modes, 13 performance/SLO, 14 observability

Affected: `backend/app/services/safety_gate_reserve.py:94`, `backend/app/services/neuro_commenting/sender_service.py:541`, `backend/tests/test_safety_gate_reserve.py:166`, `backend/tests/test_safety_gate_reserve.py:341`

Found by: Semble search for Redis fallback paths; targeted static reads of safety gate reserve and sender service.

Description: `reserve()` catches `RedisError` and returns `reserved=True` with a comment saying fail-open. `SenderService._try_gate_reserve()` also returns `None` when no Redis client is available, and `_block_by_safety_gate()` treats that as allowed. Existing tests encode both behaviors.

Reproduction expected/actual:

- Expected: if Redis is unavailable for a safety-critical concurrency gate, live send should fail closed or move to an explicit degraded mode with operator-visible signal.
- Actual: Redis errors and missing Redis allow the send path to continue without the per-account gate reservation.

Impact: During Redis outage or partial Redis failure, safety gate concurrency protection can silently disappear, allowing parallel sends for the same account/intent. This can amplify Telegram risk exactly when the control plane is degraded.

Suggested fix: For live sending, make gate reserve Redis failure fail closed by default. If a fail-open mode is still needed for local/dev, guard it behind an explicit config flag and emit a metric/log with alert coverage. Consider DB-backed degraded reservation if Redis outage tolerance is required.

Effort: Medium

### F-302 Grafana quarantine fraction uses `total_accounts`, but exporter emits `account_total`

Severity: P1

Dimension: 14 observability

Affected: `docs/grafana/safety-pipeline.json:198`, `backend/app/observability/safety_metrics.py:73`, `docs/runbooks/safety-alerts.md:17`, `docs/runbooks/safety-alerts.md:67`

Found by: `rg` for metric names across Grafana/runbook/metrics source; targeted JSON parse of `docs/grafana/safety-pipeline.json`.

Description: The Grafana dashboard panel "Quarantine Fraction" divides by `total_accounts`, but the Prometheus exporter defines and the runbook alert uses `account_total`. The dashboard JSON is valid, but this panel query references a non-existent metric.

Reproduction expected/actual:

- Expected: dashboard and alert rule use the same denominator metric emitted by `SafetyMetrics.account_total()`.
- Actual: runbook alert uses `account_total`; Grafana panel uses `total_accounts`.

Impact: The quarantine fraction panel will show no data or an invalid ratio, hiding the main quarantine epidemic SLO in the dashboard even while the Alertmanager expression is correct.

Suggested fix: Change the Grafana expression to `account_total{workspace_id=~"$workspace"}` and add a test or script that validates Grafana PromQL metric names against the exporter/runbook list.

Effort: Small

### F-303 `account_total` gauge refreshes only on quarantine mutations

Severity: P2

Dimension: 14 observability

Affected: `backend/app/services/account_quarantine.py:120`, `backend/app/services/account_quarantine.py:148`, `backend/app/services/account_quarantine.py:227`, `docs/runbooks/safety-alerts.md:62`

Found by: targeted static reads of `SafetyMetrics.account_total()` call sites and quarantine alert denominator.

Description: `account_total` is emitted only from `_refresh_quarantine_active()`, which is called when quarantine rows are opened/released/admin-overridden. Account imports, deletions, workspace account growth, and normal account lifecycle changes do not refresh the gauge.

Reproduction expected/actual:

- Expected: the denominator for `quarantine_active / account_total` is refreshed independently of quarantine mutations or collected on scrape/scheduled interval.
- Actual: the denominator can remain stale until the next quarantine mutation for that workspace/reason.

Impact: `QuarantineEpidemic` and dashboard ratios can be wrong after account count changes. A workspace could appear healthier or worse than reality, affecting rollback decisions.

Suggested fix: Add a periodic metrics collector for account totals per workspace, or compute the denominator from a DB-backed scrape endpoint/task that refreshes regardless of quarantine changes. Keep per-workspace cardinality bounded.

Effort: Medium

### F-304 Weak-GGR alert math uses histogram buckets as population growth

Severity: P2

Dimension: 13 performance/SLO, 14 observability

Affected: `backend/app/observability/safety_metrics.py:91`, `backend/app/services/ggr_calculator.py:330`, `docs/runbooks/safety-alerts.md:78`, `docs/grafana/safety-pipeline.json:295`

Found by: targeted static reads of GGR metric definition, GGR emission, runbook alert, and Grafana panel query.

Description: `ggr_score` is a Prometheus histogram labeled with a logical `bucket` value such as `weak`. The alert/dashboard query uses `increase(ggr_score_bucket{bucket="weak"}[1h])` to represent weak-account growth. Prometheus histogram `_bucket` series are cumulative over `le` buckets, so summing without `le` control can multiply observations. It also counts recalculation observations, not distinct weak accounts.

Reproduction expected/actual:

- Expected: weak GGR growth alert counts distinct accounts entering the weak bucket or exposes a dedicated gauge/counter for weak account transitions.
- Actual: alert counts histogram observation bucket increases, which can over-count recalculations and cumulative `le` buckets.

Impact: `GgrWeakBucketGrowth` can false-page or miss real weak-account population changes. Operators may roll back or hold rollout based on misleading data.

Suggested fix: Add a dedicated metric such as `ggr_bucket_account_total{workspace_id,bucket}` gauge and/or `ggr_bucket_transitions_total{workspace_id,from_bucket,to_bucket}` counter. Update runbook/Grafana to use those metrics. Keep the histogram for score distribution only.

Effort: Medium

### F-305 Redis outage can turn safety-gate cache/budget into DB cold-call stampede

Severity: P2

Dimension: 5 failure modes, 13 performance/SLO

Affected: `backend/app/services/account_safety_gate.py:117`, `backend/app/services/account_safety_gate.py:148`, `backend/app/services/account_safety_gate.py:513`, `backend/app/services/safety_gate_cache.py:48`

Found by: targeted static reads of `AccountSafetyGate.evaluate()`, Redis cache, and cold-call budget tests.

Description: `RedisSafetyGateCache.get()` returns `None` on `RedisError`; `_enforce_cold_call_budget()` returns `True` on `RedisError`. That means Redis outage disables both cache hits and the one-cold-call-per-minute throttle. The cold path then computes policy/GGR/warmup/status/cross-module checks via DB queries for every request.

Reproduction expected/actual:

- Expected: Redis outage should preserve a bounded fallback path, stale local cache, fail-closed behavior, or explicit service-degraded response.
- Actual: Redis errors bypass cache and budget, so every safety gate request can become a DB cold call.

Impact: A Redis outage can cascade into DB load and p95 regression for the safety gate, increasing API latency and possibly exhausting the DB pool during incident conditions.

Suggested fix: Add a bounded process-local stale cache or circuit breaker for Redis cache errors. Treat repeated Redis failures as degraded and fail closed for high-risk intents. Emit a cache/budget failure metric and alert.

Effort: Medium

### F-306 DB pool has no explicit checkout timeout or pool metrics

Severity: P3

Dimension: 5 failure modes, 13 performance/SLO, 14 observability

Affected: `backend/app/db.py:13`, `backend/app/config.py:13`, `backend/app/config.py:15`

Found by: targeted static read of SQLAlchemy engine setup and config; `rg` for `pool_timeout` and pool metrics.

Description: Runtime DB engine config sets `pool_pre_ping`, `pool_size`, and `max_overflow`, but no explicit `pool_timeout` or checkout/checkin instrumentation. SQLAlchemy will use its default checkout timeout, and there is no safety-pipeline metric for pool saturation.

Reproduction expected/actual:

- Expected: safety-critical API/worker DB pool behavior has an explicit timeout budget and observability for checkout latency/exhaustion.
- Actual: pool timeout is implicit, and no pool saturation metric/alert was found.

Impact: Under cold-call storms, scheduler bursts, or worker concurrency, DB pool exhaustion can present as long request hangs before errors. Operators will see symptoms later in generic latency/error logs rather than a direct pool saturation signal.

Suggested fix: Add `DB_POOL_TIMEOUT_SECONDS` with a conservative default, pass `pool_timeout` to `create_engine`, and add SQLAlchemy pool checkout latency/error counters. Alert on checkout timeout rate.

Effort: Small

## Explicit No-Issue Checks

- TDLib timeout handling: profile, warmup, readonly, and neuro runtime adapters use bounded `tdlib_auth_timeout_seconds` / `tdlib_receive_timeout_seconds`; warmup adapter maps auth timeout to structured `tdlib_auth_timeout` network/runtime result.
- TDLib stuck-attempt reconcile: `run_reconcile_tick()` limits batches, uses `FOR UPDATE SKIP LOCKED`, keeps attempts in `SENDING` on TDLib errors, and has tests for found/missing/recent/error cases.
- Scheduler idempotence: scheduler enqueue functions use time-bucketed job ids with `unique=True`; warmup scheduler uses fixed workflow job ids and checks `warmup_hard_disable` plus worker flags.
- Feature-flag toggles: safety pipeline v2 is persisted on `Workspace.safety_pipeline_v2_enabled`, admin-gated, cross-tenant checked, and audited.
- Redis diagnostics: `/ready` treats Redis down as unavailable; runtime diagnostics use short Redis socket timeouts.
- Benchmarks/perf tests: `backend/tests/benchmarks/test_safety_gate_perf.py` covers cache-hit, cold, and reserve Lua paths; baseline JSON exists with sub-SLO mean values in the checked-in baseline.
- Metrics endpoint guard: `/metrics` is mounted only when metrics are enabled and requires `X-Internal-Scrape` unless public metrics are explicitly allowed.
- Cardinality: flood-wait metric hashes account ids to an 8-character `account_id_hash`; no raw account id label was found for that metric.
- Grafana JSON: `docs/grafana/safety-pipeline.json` parses as JSON and contains 9 panels; one panel query has the metric-name defect in F-302.

## Evidence Commands

- `Get-Content .mex/ROUTER.md`, `.mex/context/{architecture,workers,backend,warmup,security}.md`, and relevant patterns.
- Semble searches for Redis fallbacks, TDLib timeout/reconcile, DB pool handling, benchmarks, metrics, alerts, and Grafana.
- `rg`/targeted `Get-Content` reads over `backend/app`, `backend/tests`, `docs/runbooks`, and `docs/grafana`.
- `ConvertFrom-Json` parse of `docs/grafana/safety-pipeline.json`.
