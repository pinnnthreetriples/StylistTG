# Research: Account Preparation Module

## Decision: Use existing TDLib/RQ execution boundary; no Telethon

**Rationale**: The project already has a TDLib-based execution model, runtime diagnostics, account locks, and RQ workers. Adding Telethon would create a second Telegram runtime, second session model, and duplicate error semantics.

**Alternatives considered**:
- Telethon workers: rejected due to runtime duplication and session risk.
- Raw Telegram client in API handlers: rejected because handlers must not perform Telegram execution.

## Decision: Use RQ queue taxonomy, not Redis lists

**Rationale**: Existing workers are RQ-based. RQ gives clearer operational integration, retries, worker launching, and diagnostics than custom `RPUSH/BLPOP` loops.

**Alternatives considered**:
- Custom Redis list queues: rejected as weaker and inconsistent with project execution-plane.
- Inline API execution: rejected because account work must remain asynchronous.

## Decision: Store idempotency in Postgres

**Rationale**: The 14-day lifecycle outlives short Redis TTL fingerprints. Postgres uniqueness on session/day/task type gives durable idempotency and auditability.

**Alternatives considered**:
- Redis fingerprints: rejected because TTL expiry can allow duplicate execution.
- In-memory worker state: rejected because workers are process-bound and not durable.

## Decision: Make proxy geo and risk score warnings

**Rationale**: Proxy risk scoring is an external heuristic and can fail or produce false positives. It is useful as diagnostic context but should not be the sole blocker.

**Alternatives considered**:
- Hard block on fraud score/geo mismatch: rejected because it would block valid operators on unstable external data.

## Decision: Dry-run worker first; live actions require separate product approval

**Rationale**: A professional module needs safe orchestration, audit, idempotency, cadence, and UI before any live actions. Behavior imitation and anti-spam evasion are out of scope.

**Alternatives considered**:
- Full live behavior automation: rejected due to safety, policy, and account-risk concerns.
- No worker until live actions exist: rejected because cadence/idempotency/audit can be built and tested safely in dry-run mode.

## Decision: Derive account warmup state by join/service, not account column

**Rationale**: Session is the source of truth. A denormalized account column risks drift and complicates future migrations.

**Alternatives considered**:
- `account.warmup_status`: rejected for drift risk.
- Materialized summary table: deferred until performance requires it.

## Decision: Polling UI only

**Rationale**: The project contract is polling-first. Active sessions can be polled at a moderate interval, while terminal sessions should not be polled.

**Alternatives considered**:
- WebSocket/SSE: rejected because it conflicts with current architecture and adds unnecessary infrastructure.

