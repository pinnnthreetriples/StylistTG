# Risk Register — Performance & Refactor Series

## Resolved Risks

| Risk | Resolution | PR |
|---|---|---|
| Snapshot freshness: `AccountSafetySnapshot` may change live semantics | Safety summary uses live queries, snapshot is write-cache only | PR 3 |
| OpenAPI churn from router splitting | Paths and schemas preserved; router split is internal only | PR 5 |
| Worker stuck in WAITING_LOCK forever | Bounded retry with `max_lock_wait_seconds`; fails with `lock_wait_timeout` | PR 6a |
| Orphaned QUEUED jobs after Redis restart | `reconcile_orphaned_queued_jobs()` detects and fails/re-enqueues | PR 6b |
| Inline fallback unsafe in cloud | Config validator rejects `QUEUE_INLINE_FALLBACK_ENABLED=true` in cloud mode | PR 6c |
| Materialization not idempotent | `rematerialize_account_update_job()` is safe to re-run | PR 6d |
| Tenant leakage via operation logs | `log_operation` workspace_id is explicit at all API boundaries | PR 8 |
| N+1 queries on account list | Batch-loaded joins; constant query count verified by ceilings | PR 2, PR 9 |

## Remaining Risks

| Risk | Severity | Mitigation | Owner |
|---|---|---|---|
| `safety-summary` still sub-linear (not constant) | Low | Ceiling test at ≤5/acct guards against regression; full constant-time would require pre-computed snapshot | Future PR |
| `tdlib_proxy.py` log_operation uses fallback workspace lookup | Low | Internal worker context; no tenant-facing exposure; tracked for future cleanup | Future PR |
| Index drift between migrations and models | Low | Alembic autogenerate + nightly pyright catch schema mismatches | CI/nightly |
| Worker duplicate execution on re-enqueue | Low | Jobs check state at start; idempotent materialization; bounded retry count | PR 6a–6d |
