# Implementation Plan: Account Preparation Module

**Branch**: `001-account-preparation` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/001-account-preparation/spec.md`

## Summary

Build a professional account preparation module for StylistTG with strategies, readiness checks, 14-day preparation sessions, dry-run RQ worker execution, idempotent task runs, audit events, and a Russian-language dashboard. The module must integrate with the existing FastAPI/RQ/Redis/TDLib architecture without introducing Telethon, behavior imitation, automatic channel joins, automatic reactions, synthetic P2P messaging, or LLM message rewriting.

## Technical Context

**Language/Version**: Python 3.14+ backend, TypeScript strict frontend  
**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, Pydantic settings/schemas, RQ, Redis, React 19, TanStack Router/Query, Tailwind CSS v4, shadcn-style UI, lucide-react  
**Storage**: PostgreSQL target with SQLite-compatible tests where existing project patterns allow; Redis for queue/locks only; Postgres is source of truth for sessions and idempotency  
**Testing**: pytest/ruff for backend; Vitest, TypeScript, ESLint, Vite build for frontend; OpenAPI type generation/checks for contracts  
**Target Platform**: Windows local workstation and cloud/staging backend workers  
**Project Type**: Full-stack web application with API, background workers, and dashboard UI  
**Performance Goals**: Session list and details remain responsive for normal operator use; active status polling avoids terminal sessions; worker advances at most one day per due session per run  
**Constraints**: No live Telegram calls in this feature; no client exposure of secrets/session material; no WebSocket/SSE; no second Telegram runtime; no raw Redis queue implementation  
**Scale/Scope**: Single-workspace local use and SaaS workspace-scoped use; one active preparation session per account per workspace; 14-day session lifecycle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution template is not filled with project-specific principles. Project-specific gates are taken from `AGENTS.md` and `AGENT_HANDOFF.md`:

- **Simplicity and scope**: Pass. The module is split into backend schema/API, dry-run worker, frontend, and seeds. Unsafe automation is excluded.
- **Surgical integration**: Pass. Reuse existing FastAPI, RQ, Redis, workspace, audit, diagnostics, and frontend routing/query patterns.
- **Postgres source of truth**: Pass. Session state and task idempotency live in Postgres, not Redis fingerprints.
- **Polling-first UI**: Pass. No WebSocket/SSE.
- **TDLib safety**: Pass. No live Telegram calls in this feature; future live actions require separate product decision.
- **Secrets boundary**: Pass. No endpoint returns auth secrets, session material, API hashes, proxy credentials, or raw runtime paths.
- **Test-first quality**: Pass with implementation requirement. Each PR must add focused tests before production behavior.

Post-design re-check: Pass. Design artifacts preserve the same boundaries.

## Project Structure

### Documentation (this feature)

```text
specs/001-account-preparation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── warmup-api.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── warmup.py
│   │   └── accounts.py              # derived warmup info on account responses
│   ├── services/
│   │   ├── warmup.py                # session/readiness/application service
│   │   ├── warmup_readiness.py      # pre-flight checks
│   │   ├── warmup_worker.py         # dry-run step service
│   │   └── operation_locks.py       # reuse existing lock patterns if applicable
│   ├── workers/
│   │   ├── run_worker.py            # add warmup_jobs allowlist
│   │   └── warmup_jobs.py           # RQ entrypoint
│   ├── models.py                    # add ORM models for warmup tables
│   ├── schemas/
│   │   └── warmup.py
│   └── config.py                    # settings for feature flags and thresholds
├── migrations/
│   └── versions/
│       └── 20260505_0023_account_preparation_warmup.py
└── tests/
    ├── test_warmup_migration_contract.py
    ├── test_warmup_readiness.py
    ├── test_warmup_sessions_api.py
    ├── test_warmup_worker.py
    └── test_warmup_account_integration.py

apps/dashboard/src/
├── routes/
│   └── WarmupRoute.tsx
├── modules/warmup/
│   ├── WarmupModule.tsx
│   ├── api.ts
│   ├── types.ts
│   ├── hooks.ts
│   └── components/
│       ├── WarmupReadinessBanner.tsx
│       ├── WarmupSessionsTable.tsx
│       ├── WarmupCreateWizard.tsx
│       ├── WarmupSessionDetail.tsx
│       ├── WarmupStatusBadge.tsx
│       └── WarmupEventLog.tsx
├── lib/
│   ├── routes.ts
│   ├── queries.ts
│   └── uiLabels.ts
└── router.tsx

packages/api-client/
└── generated OpenAPI types after backend contract is added
```

**Structure Decision**: Use the existing full-stack monorepo shape. Backend owns all data access and execution. Frontend uses generated/typed API client patterns and TanStack Router/Query. Worker execution uses RQ and existing worker launcher conventions.

## Complexity Tracking

No constitution violations requiring complexity exceptions.

## Implementation Slices

### Slice 1: Schema and ORM Foundation

Goal: Persist strategies, sessions, task runs, and events with workspace scope and idempotency.

Deliverables:
- Alembic migration for four tables.
- SQLAlchemy models and enums/string constants matching migration.
- Migration contract test that applies schema and inspects tables, columns, FK, unique constraints, and partial indexes.

Verification:
- `cd backend; python -m pytest tests/test_warmup_migration_contract.py -q`
- `cd backend; python -m alembic heads`
- `cd backend; python -m alembic upgrade 20260503_0022:20260505_0023 --sql`
- `cd backend; python -m ruff check migrations/versions/20260505_0023_account_preparation_warmup.py tests/test_warmup_migration_contract.py`

### Slice 2: Backend API Foundation

Goal: Provide typed schemas and API endpoints for readiness, sessions, pause/resume, events, strategies, and module readiness.

Deliverables:
- `backend/app/schemas/warmup.py`
- `backend/app/services/warmup_readiness.py`
- `backend/app/services/warmup.py`
- `backend/app/api/warmup.py`
- Router registered in `backend/app/main.py`
- OpenAPI generation remains current.

Verification:
- Readiness tests for pass, blocker, warning-only, active-session blocker, unavailable system dependency.
- Session API tests for create, 422 on blockers, list/detail/status, pause, resume, early resume conflict, event listing.
- `cd backend; python -m pytest tests/test_warmup_readiness.py tests/test_warmup_sessions_api.py -q`
- `cd backend; python -m ruff check .`

### Slice 3: Dry-Run RQ Worker

Goal: Advance due sessions safely without Telegram API calls.

Deliverables:
- Add `warmup_jobs` to worker queue allowlist/taxonomy.
- Worker job that finds due sessions, obtains account lock, records task run, writes events, advances one day, schedules next step, handles completion.
- Circuit breaker for repeated internal failures.
- No Telegram API, no TDLib live calls, no Telethon.

Verification:
- Due session advances one day only.
- Not-due session is skipped.
- Duplicate task run is idempotently skipped.
- Day 14 completes.
- Failure threshold trips circuit breaker.
- `cd backend; python -m pytest tests/test_warmup_worker.py -q`

### Slice 4: Account Integration and Operation Policy

Goal: Surface derived preparation state on account reads and prevent conflicting operator actions where appropriate.

Deliverables:
- Account response includes derived `warmup` object for non-terminal sessions.
- Operation policy helper defines which account actions are blocked or warned while preparation is active.
- No `account.warmup_status` database column.

Verification:
- Account API test confirms derived warmup object.
- Conflicting action tests confirm block/warning behavior and audit metadata.
- `cd backend; python -m pytest tests/test_warmup_account_integration.py -q`

### Slice 5: Frontend Module

Goal: Provide a complete Russian-language operator UI.

Deliverables:
- Route `/modules/warmup`.
- Module dashboard with dry-run/readiness banner, table, status badges, progress, next step, updated time.
- Create wizard: account selection, strategy selection, readiness result, create confirmation.
- Session detail with event log.
- Pause/resume actions.
- Query keys integrated into existing query helper patterns.

Verification:
- Frontend unit tests for hooks/state helpers.
- Build/lint/test.
- Browser QA screenshot for dashboard and wizard.
- `npm run lint`
- `npm run test`
- `npm run build`

### Slice 6: Preset Strategies and Documentation

Goal: Ship usable default strategies and operator docs.

Deliverables:
- Seed script or migration-safe seed routine for preset strategies.
- `.env.example` entries for feature flags and worker thresholds.
- Runbook section for local worker startup and dry-run behavior.

Verification:
- Seed idempotency test.
- Strategies visible through API/UI.
- Docs do not imply anti-ban guarantees.

## Risk Controls

- No live Telegram calls in this feature.
- No behavior imitation: no automatic online status, stories browsing, channel joins, reactions, P2P, or LLM message rewriting.
- Proxy score and geo mismatch are warnings.
- Every state transition writes a preparation event.
- Worker state changes are idempotent through `warmup_task_run`.
- Worker respects cadence and cannot fast-forward 14 days.
- Account lock prevents concurrent processing for the same account.
- UI copy uses neutral safety wording, not anti-ban promises.

