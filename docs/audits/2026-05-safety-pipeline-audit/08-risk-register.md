# Risk Register

Risk scoring: severity first, then likelihood. No P0 was found. Verdict therefore depends on whether P1 conditions are accepted before production live enablement.

| Rank | Risk | Severity | Likelihood | Findings | Mitigation |
| --- | --- | --- | --- | --- | --- |
| 1 | Non-flood send errors leave attempts in `SENDING` | P1 | likely | F-001 | Finalize all send error branches through one failure finalizer and add regression test. |
| 2 | Unexpected sender exceptions leak rate/gate reservations until TTL | P1 | possible | F-002 | Use `finally` cleanup for reservations around live send. |
| 3 | Redis-down gate reserve fails open for live send concurrency | P1 | possible | F-301 | Fail closed for live send or require explicit degraded fail-open flag plus alert. |
| 4 | Account deletion blocked by safety-table FK rows | P1 | likely | F-E001 | Add cascade or explicit cleanup for account-owned safety tables. |
| 5 | Migration replay/downgrade not proven on disposable >=10k dataset | P1 | possible | F-E002 | Build replay job and record timings/count deltas. |
| 6 | Sensitive redaction misses email/phone PII | P1 | possible | B F-001 | Extend redactor keys/regexes and audit API tests. |
| 7 | Metrics tests hard-require optional `prometheus_client` | P1 | likely local / possible CI | F-041 | Require dependency or `importorskip` metrics-only tests. |
| 8 | GGR warmup/profile reads not consistently workspace constrained | P1 | unlikely normal / possible repair scripts | F-003 | Add workspace predicate/invariant tests; consider profile workspace field. |
| 9 | Grafana quarantine fraction uses non-existent metric | P1/P2 | likely | F-302, F-006-002 | Use `account_total`; validate dashboard queries against emitted metrics. |
| 10 | Redis outage disables cache and cold-call budget, causing DB stampede | P2 | possible | F-305 | Circuit breaker or bounded local stale cache; alert Redis-cache failures. |
| 11 | Weak-GGR alert counts histogram observations, not weak accounts | P2 | possible | F-304 | Add dedicated weak-account total/transition metrics. |
| 12 | Runtime DB/Redis clients lack explicit timeout caps | P2 | possible | F-E004, F-306 | Add DB pool/connect/query and Redis socket timeout settings/metrics. |
| 13 | Quarantine creation allows overlapping active quarantines | P2 | possible | F-005 | Idempotent active quarantine extension or partial unique index. |
| 14 | Status monitor tick is unbounded and lock-free | P2 | possible at scale | F-006 | Add limit, checkpoint, and singleton/skip-locked strategy. |
| 15 | Reconcile context does not validate observed/target campaign ownership | P2 | unlikely normal / possible corrupt data | F-004 | Load via workspace/campaign-scoped predicates. |
| 16 | AccountSafetyOverride is not workspace-scoped / semgrep-covered | P2 | possible future regression | B F-002, B F-003 | Add workspace column/predicate or documented invariant and static rule. |
| 17 | Lua reserve counter remains inflated after reservation key expiry | P2 | possible crash path | B F-004 | Symmetric live-reservation count via set/zset or TTL parity. |
| 18 | Backfill has check-then-insert race and non-stable seed | P2 | possible operator overlap | B F-005, F-E005 | Upsert/lock per workspace; deterministic hash seed. |
| 19 | E2E gate call-count test is self-fulfilling | P2 | likely hidden regression | F-042 | Count calls from real workflow boundaries. |
| 20 | Behavior emulator is not wired into live sender | P2 | likely expectation drift | F-008 | Wire behavior-aware sender or document live rollout scope. |

## Pareto View

Fastest risk reduction before canary:

1. Fix sender failure finalizer and reservation cleanup.
2. Fix PII redaction for email/phone.
3. Fix Grafana metric mismatch.
4. Decide account deletion policy for safety tables.
5. Make `prometheus_client` dependency/test behavior deterministic.

Deep work before wider rollout:

1. Disposable migration replay job.
2. Redis degraded-mode design.
3. Workspace-scoped safety override model.
4. Status monitor batching/locking.
5. Dedicated GGR bucket population metrics.
