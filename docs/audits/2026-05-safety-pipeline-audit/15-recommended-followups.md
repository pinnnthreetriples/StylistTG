# Recommended Follow-up Issues

Draft issue bodies only. Do not create these automatically; operator should choose priority/order.

## P1 Follow-ups

### P1-1: Fix live sender failure finalization and reservation cleanup

**Goal**: Ensure every live send failure leaves attempts and reservations in a correct state.

**Scope**: `backend/app/services/neuro_commenting/sender_service.py`, sender tests.

**Acceptance criteria**:

- Non-flood `TelegramCommentSendError` marks attempt failed or repairable with `failed_at`.
- Unexpected exceptions release safety gate and rate reservations.
- Regression tests cover non-flood and unexpected exception paths.

**References**: F-001, F-002.

### P1-2: Define Redis-degraded behavior for safety gate reserve/cache/budget

**Goal**: Prevent Redis outages from silently removing live-send safety controls or causing DB cold-call storms.

**Scope**: `safety_gate_reserve.py`, `safety_gate_cache.py`, `account_safety_gate.py`, metrics/alerts.

**Acceptance criteria**:

- Live send fails closed or uses explicit operator-approved degraded mode.
- Redis cache/budget errors are bounded and observable.
- Tests cover Redis errors and TTL expiry behavior.

**References**: F-301, F-305, B F-004.

### P1-3: Make account deletion work with safety-pipeline artifacts

**Goal**: Account hard delete is reliable after safety pipeline v2 writes derived tables.

**Scope**: Account deletion service, safety table FKs/migrations/tests.

**Acceptance criteria**:

- Account deletion with GGR, behavior, quarantine, observations, load buckets, bought onboarding state succeeds.
- Retained audit/event policy is documented.
- Regression test covers all account-owned safety tables.

**References**: F-E001.

### P1-4: Run and document disposable migration replay

**Goal**: Prove migration chain upgrade/downgrade/upgrade on synthetic >=10k-account dataset.

**Scope**: migration replay script/job, `11-migration-replay-log.md`.

**Acceptance criteria**:

- Disposable Postgres replay uses synthetic account/safety rows.
- Timings and row-count deltas are recorded.
- Lossy downgrade limitations are documented.

**References**: F-E002, F-E003, F-E006.

### P1-5: Redact email and phone PII in sensitive audit metadata

**Goal**: Sensitive audit/log metadata does not persist raw emails or phone numbers.

**Scope**: `secret_redaction.py`, `sensitive_audit.py`, audit API tests.

**Acceptance criteria**:

- Email and phone keys are masked.
- Email/phone patterns inside strings are masked.
- Regression tests cover metadata, reason strings, and serialized audit responses.

**References**: B F-001.

### P1-6: Stabilize metrics dependency in backend test environment

**Goal**: Full backend collection is not blocked by optional Prometheus dependency.

**Scope**: backend dependencies and/or metrics tests.

**Acceptance criteria**:

- `pytest tests --ignore=tests/contract --ignore=tests/benchmarks --collect-only -q` collects cleanly.
- Metrics-specific tests either require installed `prometheus_client` or skip clearly.

**References**: F-041.

## P2/P3 Follow-ups

### P2-1: Fix Grafana quarantine fraction metric

Replace `total_accounts` with emitted `account_total` and add dashboard metric-name validation. References: F-302, F-006-002.

### P2-2: Add dedicated GGR weak-bucket population metrics

Expose weak-account totals/transitions instead of deriving population from histogram buckets. Reference: F-304.

### P2-3: Make active quarantine creation idempotent

Reuse/extend active quarantine rows per workspace/account/reason or add safe uniqueness semantics. Reference: F-005.

### P2-4: Batch and lock account status monitor ticks

Add limit/checkpoint/singleton or skip-locked strategy for production scheduler runs. Reference: F-006.

### P2-5: Workspace-scope `AccountSafetyOverride`

Add `workspace_id` or explicit account-join invariant plus semgrep coverage. References: B F-002, B F-003.

### P2-6: Replace self-fulfilling E2E gate count with workflow-driven assertions

Run real live-readiness/sender/warmup/editing/API paths under gate spy. Reference: F-042.

### P2-7: Wire or explicitly defer behavior-aware live sender

Either integrate human behavior emulator into live sender or state that rollout is safety-gated direct sender only. Reference: F-008.

### P2-8: Make backfill concurrency-idempotent and deterministic

Use upsert/lock and replace Python `hash()` seed with deterministic hash. References: B F-005, F-E005.

### P2-9: Add DB/Redis timeout caps and pool metrics

Add DB pool/connect/query timeouts, Redis socket timeouts, and pool saturation metrics. References: F-E004, F-306.

### P2-10: Validate reconcile context ownership

Load observed posts and targets through campaign/workspace-scoped predicates. Reference: F-004.

### P2-11: Add safety-policy override checkbox in dashboard quarantine release

Expose `override_gate_block` in `QuarantineStateBanner` and test payload. Reference: F-006-001.

### P3-1: Move safety-pipeline time calls to `utc_now()`

Replace direct `datetime.now(UTC)` in boundary-sensitive safety paths with shared helper or injected `now`. References: F-007, F-006-004.

### P3-2: Use generated OpenAPI client methods for safety-policy wrappers

Switch raw request wrappers to generated GET/PATCH calls. Reference: F-006-003.
