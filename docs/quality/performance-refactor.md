# Performance & Refactor Decisions

Summary of optimizations and architectural changes made in PRs 1–9.

## PR 1: Hot-path indexes + query-count foundation

- Added composite database indexes on frequently queried columns (`Job.account_id + job_state`, `AccountOperationLog.account_id + created_at`).
- Introduced `QueryCounter` test helper to measure SQL statements per endpoint.
- Established baseline query counts for hot-path endpoints.

## PR 2: Optimize `/api/accounts` N+1

- Replaced per-account queries for warmup policy and profile photo with batch-loaded joins.
- `/api/accounts` query count is now **constant** (7 queries) regardless of account count.

## PR 3: Optimize safety/risk summaries

- `/api/accounts/risk-summary` runs in constant queries (7).
- `/api/accounts/safety-summary` scales sub-linearly (≤5 queries per account).

## PR 4: Scoped account/job helpers

- All account and job lookups enforce `workspace_id` scoping where callers have it.
- Prevents cross-workspace data leakage by design.

## PR 5: Split account routers by domain

- Account API split into domain-specific routers (runtime, safety, lifecycle, compat).
- No OpenAPI contract changes — paths and schemas preserved.

## PR 6a–6d: Worker reliability hardening

- **6a**: Bounded lock-wait retry with `max_lock_wait_seconds` / `lock_retry_delay_seconds`. Jobs fail with `lock_wait_timeout` instead of getting stuck.
- **6b**: `reconcile_orphaned_queued_jobs()` detects QUEUED jobs missing from Redis and re-enqueues or fails them with `queue_lost`.
- **6c**: Cloud config validation rejects `QUEUE_INLINE_FALLBACK_ENABLED=true` in production.
- **6d**: `rematerialize_account_update_job()` provides idempotent post-materialization recovery.

## PR 7: Shared job creation orchestration

- Extracted `validate_account_for_job()` (account lookup + hard-stop + execution-usable check) and `finalize_job_creation()` (add + audit + usage + commit + log).
- Both `create_profile_job` and `create_account_update_job` use shared helpers.
- No behavior or API contract changes.

## PR 8: Operation log and lifecycle boundary hardening

- `log_operation()` accepts explicit `workspace_id` parameter; skips DB lookup when provided.
- All API-layer and worker call sites pass explicit workspace_id.
- Internal/background call sites (tdlib_proxy) use transitional fallback.
- Export and deletion requests are workspace-scoped and tested.

## PR 9: Final tightening

- Strict query-count ceilings protect all optimized endpoints.
- Worker reconciliation and lock-retry logic covered by regression tests.
- Risk register updated with resolved and remaining items.

## Query-Count Ceilings

| Endpoint | Ceiling | Measured |
|---|---|---|
| `GET /api/accounts` (20 accts) | ≤10 | 7 |
| `GET /api/accounts/risk-summary` (10 accts) | ≤10 | 7 |
| `GET /api/accounts/safety-summary` (10 accts) | ≤5/acct | 3.2/acct |
| `GET /api/auth-batches/{id}` | ≤10 | 6 |
| `GET /api/jobs/{id}` | ≤10 | 6 |
