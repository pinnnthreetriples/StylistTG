# Cross-task Dependency Graph

```mermaid
flowchart TD
  T11["Task 11: GGR Calculator"] --> T13["Task 13: AccountSafetyGate"]
  T12["Task 12: AccountQuarantine"] --> T13
  T15["Task 15: AccountStatusMonitor"] --> T12
  T17["Task 17: CrossModuleLoadTracker"] --> T13
  T19["Task 19: Gate callsites"] --> Live["Live readiness / sender / warmup / editing"]
  T22["Task 22: Redis Lua reserve"] --> Sender["Neuro sender"]
  T23["Task 23: Rate limiter fallback"] --> Sender
  T24["Task 24: Reconcile stuck attempts"] --> Sender
  T25["Task 25: Tenant scope"] --> T32["Task 32: Admin overrides"]
  T26["Task 26: Sensitive audit"] --> AuditAPI["Audit API / operator review"]
  T28["Task 28: Backfill"] --> T11
  T29["Task 29: Migration safety"] --> Rollout["Task 40: Production rollout"]
  T30["Task 30: Observability"] --> Rollout
  T39["Task 39: Docs"] --> Rollout
  T41["Task 41: GGR cleanup"] --> T11
```

## High-impact Dependency Chains

| Chain | Risk |
| --- | --- |
| Task 22 Redis reserve -> Task 19 sender -> Task 40 rollout | Redis failure can fail open for live send concurrency and fail cold-call budget, weakening safety exactly during degraded infrastructure. |
| Task 11 GGR -> Task 13 gate -> Task 19 callsites | Workspace-mismatched GGR inputs can cause false allow/block decisions across all gate users. |
| Task 12 quarantine -> Task 30 observability -> Task 40 rollout | Duplicate quarantines/stale denominator/broken Grafana query can make operator rollout signals wrong. |
| Task 24 reconcile -> Task 19 sender | Sender leaves attempts stuck; reconcile can recover later, but context validation gaps can misclassify corrupt attempts. |
| Task 25 tenant scope -> Task 32 safety overrides | Override rows are account-owned but not workspace-scoped or covered by semgrep, increasing future admin-control regression risk. |
| Task 26 sensitive audit -> audit APIs/docs | Email/phone PII redaction gap affects admin mutation audit rows and any operator-visible metadata. |
| Task 28/29 migrations/backfill -> Task 40 rollout | Replay not proven, backfill has race/non-deterministic seed, and some downgrades are lossy. |
| Task 14 behavior emulator -> Task 19 live sender | Behavior foundation exists, but live sender does not use behavior-aware sequencing. |

## Quick Wins

1. Sender finalizer for all error paths.
2. Redaction regex/key expansion.
3. Grafana metric rename.
4. `prometheus_client` dependency/test skip decision.
5. Dashboard checkbox for `override_gate_block`.

## Deep Refactors

1. Account lifecycle/cascade policy for safety tables.
2. Redis degraded-mode and reservation counter redesign.
3. Workspace-scoped `AccountSafetyOverride`.
4. Status monitor batching/scheduler locking.
5. Disposable migration replay harness.
