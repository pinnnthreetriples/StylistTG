# Tasks: Account Preparation Module

**Input**: Design documents from `specs/001-account-preparation/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/warmup-api.md`, `quickstart.md`

## Phase 1: Setup

- [X] T001 Confirm working branch is `001-account-preparation` with `git status --short --branch`
- [X] T002 [P] Review current backend worker queue taxonomy in `backend/app/workers/run_worker.py`
- [X] T003 [P] Review current API router registration in `backend/app/main.py`
- [X] T004 [P] Review frontend route and query patterns in `apps/dashboard/src/router.tsx` and `apps/dashboard/src/lib/queries.ts`
- [X] T005 [P] Review OpenAPI generation flow in `packages/api-client` and root `package.json`

## Phase 2: Foundational

- [X] T006 Add SQLAlchemy warmup models in `backend/app/models.py`
- [X] T007 Add warmup settings defaults in `backend/app/config.py`
- [X] T008 Add warmup schemas in existing `backend/app/schemas.py`
- [X] T009 Add warmup event writer helper in `backend/app/services/warmup.py`
- [X] T010 Add warmup route registration placeholder in `backend/app/api/warmup.py`
- [X] T011 Register warmup router in `backend/app/main.py`
- [X] T012 Add generated API contract update command to verification notes in `specs/001-account-preparation/quickstart.md`

## Phase 3: User Story 1 - Check Account Readiness (P1)

**Goal**: Operator can run readiness and see blockers separately from warnings.

**Independent Test**: Backend readiness tests pass for ready, blocked, and warning-only cases.

- [X] T013 [P] [US1] Write readiness pass test in `backend/tests/test_warmup_readiness.py`
- [X] T014 [P] [US1] Write active-session blocker test in `backend/tests/test_warmup_readiness.py`
- [X] T015 [P] [US1] Write proxy warning-only test in `backend/tests/test_warmup_readiness.py`
- [X] T016 [US1] Implement readiness check result models in `backend/app/schemas.py`
- [X] T017 [US1] Implement readiness service in `backend/app/services/warmup_readiness.py`
- [X] T018 [US1] Implement `POST /api/warmup/validate` in `backend/app/api/warmup.py`
- [X] T019 [US1] Run `cd backend; python -m pytest tests/test_warmup_readiness.py -q`

## Phase 4: User Story 2 - Create a 14-Day Preparation Session (P1)

**Goal**: Operator can create a scheduled session only after server-side readiness passes.

**Independent Test**: Session API tests pass for create, duplicate active session, and blocked readiness.

- [X] T020 [P] [US2] Write successful session creation test in `backend/tests/test_warmup_sessions_api.py`
- [X] T021 [P] [US2] Write blocked session creation test in `backend/tests/test_warmup_sessions_api.py`
- [X] T022 [P] [US2] Write duplicate active session conflict test in `backend/tests/test_warmup_sessions_api.py`
- [X] T023 [US2] Implement session create service in `backend/app/services/warmup.py`
- [X] T024 [US2] Implement `POST /api/warmup/sessions` in `backend/app/api/warmup.py`
- [X] T025 [US2] Ensure session creation writes `session_created` event in `backend/app/services/warmup.py`
- [X] T026 [US2] Run `cd backend; python -m pytest tests/test_warmup_sessions_api.py -q`

## Phase 5: User Story 3 - Monitor Progress and Events (P1)

**Goal**: Operator can list sessions, inspect details, poll status, and view event history.

**Independent Test**: API list/detail/status/events tests pass and return sanitized data.

- [X] T027 [P] [US3] Write session list/detail/status tests in `backend/tests/test_warmup_sessions_api.py`
- [X] T028 [P] [US3] Write event listing test in `backend/tests/test_warmup_sessions_api.py`
- [X] T029 [US3] Implement session list/detail/status services in `backend/app/services/warmup.py`
- [X] T030 [US3] Implement events service in `backend/app/services/warmup.py`
- [X] T031 [US3] Implement `GET /api/warmup/sessions`, `GET /api/warmup/sessions/{session_id}`, and `GET /api/warmup/sessions/{session_id}/status` in `backend/app/api/warmup.py`
- [X] T032 [US3] Implement `GET /api/warmup/sessions/{session_id}/events` in `backend/app/api/warmup.py`
- [X] T033 [US3] Run `cd backend; python -m pytest tests/test_warmup_sessions_api.py -q`

## Phase 6: User Story 4 - Pause and Resume Safely (P2)

**Goal**: Operator can pause and resume sessions while respecting retry/cadence rules.

**Independent Test**: Pause/resume API tests pass for success, terminal conflict, and early retry conflict.

- [X] T034 [P] [US4] Write pause success and terminal conflict tests in `backend/tests/test_warmup_sessions_api.py`
- [X] T035 [P] [US4] Write resume success and future retry conflict tests in `backend/tests/test_warmup_sessions_api.py`
- [X] T036 [US4] Implement pause service with required reason in `backend/app/services/warmup.py`
- [X] T037 [US4] Implement resume service with retry gate in `backend/app/services/warmup.py`
- [X] T038 [US4] Implement `PUT /api/warmup/sessions/{session_id}/pause` and `PUT /api/warmup/sessions/{session_id}/resume` in `backend/app/api/warmup.py`
- [X] T039 [US4] Run `cd backend; python -m pytest tests/test_warmup_sessions_api.py -q`

## Phase 7: User Story 5 - Execute Dry-Run Daily Steps (P2)

**Goal**: RQ worker advances due sessions safely without Telegram API calls.

**Independent Test**: Worker tests pass for due, not-due, duplicate, completion, lock, and circuit breaker cases.

- [X] T040 [P] [US5] Write due-session one-day advancement test in `backend/tests/test_warmup_worker.py`
- [X] T041 [P] [US5] Write not-due skip test in `backend/tests/test_warmup_worker.py`
- [X] T042 [P] [US5] Write duplicate task-run idempotency test in `backend/tests/test_warmup_worker.py`
- [X] T043 [P] [US5] Write day-14 completion test in `backend/tests/test_warmup_worker.py`
- [X] T044 [P] [US5] Write circuit-breaker test in `backend/tests/test_warmup_worker.py`
- [X] T045 [US5] Add `warmup_jobs` to worker allowlist in `backend/app/workers/run_worker.py`
- [X] T046 [US5] Implement dry-run step service in `backend/app/services/warmup_worker.py`
- [X] T047 [US5] Implement RQ entrypoint in `backend/app/workers/warmup_jobs.py`
- [X] T048 [US5] Ensure worker writes task-run and event records in `backend/app/services/warmup_worker.py`
- [X] T049 [US5] Run `cd backend; python -m pytest tests/test_warmup_worker.py -q`

## Phase 8: User Story 6 - Use Preset Strategies (P3)

**Goal**: Operator can select safe built-in strategies.

**Independent Test**: Strategy API returns presets and seed is idempotent.

- [X] T050 [P] [US6] Write strategy listing test in `backend/tests/test_warmup_strategies.py`
- [X] T051 [P] [US6] Write preset seed idempotency test in `backend/tests/test_warmup_strategies.py`
- [X] T052 [US6] Implement `GET /api/warmup/strategies` in `backend/app/api/warmup.py`
- [X] T053 [US6] Implement idempotent strategy seed in `backend/app/scripts/seed_warmup_strategies.py`
- [X] T054 [US6] Add safe preset strategy copy in `backend/app/scripts/seed_warmup_strategies.py`
- [X] T055 [US6] Run `cd backend; python -m pytest tests/test_warmup_strategies.py tests/test_warmup_sessions_api.py -q`

## Phase 9: Account Integration and Operation Policy

- [X] T056 [P] Write account derived warmup state test in `backend/tests/test_warmup_account_integration.py`
- [X] T057 [P] Write conflicting operation policy tests in `backend/tests/test_warmup_account_integration.py`
- [X] T058 Add derived warmup object to account API response in `backend/app/api/accounts.py`
- [X] T059 Add account warmup schema fields without database denormalization in `backend/app/schemas.py`
- [X] T060 Add operation policy helper for active preparation sessions in `backend/app/services/warmup.py`
- [X] T061 Run `cd backend; python -m pytest tests/test_warmup_account_integration.py -q`

## Phase 10: Frontend Module

- [X] T062 [P] Create warmup frontend types in `apps/dashboard/src/modules/warmup/types.ts`
- [X] T063 [P] Create warmup API wrapper in `apps/dashboard/src/modules/warmup/api.ts`
- [X] T064 [P] Create warmup query hooks in `apps/dashboard/src/modules/warmup/hooks.ts`
- [X] T065 Create `WarmupReadinessBanner` in `apps/dashboard/src/modules/warmup/components/WarmupReadinessBanner.tsx`
- [X] T066 Create `WarmupSessionsTable` in `apps/dashboard/src/modules/warmup/components/WarmupSessionsTable.tsx`
- [X] T067 Create `WarmupCreateWizard` in `apps/dashboard/src/modules/warmup/components/WarmupCreateWizard.tsx`
- [X] T068 Create `WarmupSessionDetail` and `WarmupEventLog` in `apps/dashboard/src/modules/warmup/components/`
- [X] T069 Create route component in `apps/dashboard/src/routes/WarmupRoute.tsx`
- [X] T070 Register `/modules/warmup` route in `apps/dashboard/src/router.tsx` and route constants in `apps/dashboard/src/lib/routes.ts`
- [X] T071 Add Russian labels/errors in `apps/dashboard/src/modules/warmup`
- [X] T072 Add frontend tests for warmup hooks or helpers in `apps/dashboard/src/modules/warmup/`
- [X] T073 Run `npm run generate:api && npm run check:api && npm run lint && npm run test && npm run build`

## Phase 11: Docs, Verification, and Polish

- [X] T074 Add warmup env examples to `.env.example` and `.env.cloud.example`
- [X] T075 Add operator runbook in `docs/runbooks/account-preparation.md`
- [X] T076 Verify no UI/backend copy promises anti-ban, shadow-ban protection, or behavior imitation in `apps/dashboard/src` and `backend/app`
- [X] T077 Run backend full check `cd backend; python -m pytest -q && python -m ruff check .`
- [X] T078 Run frontend full check `npm run lint && npm run test && npm run build`
- [X] T079 Run API contract check `npm run generate:api && npm run check:api`
- [X] T080 Review final diff for secrets, TDLib session exposure, Telethon imports, raw Redis queues, P2P tables, and LLM/spintax additions in `backend/app` and `apps/dashboard/src`

## Dependencies

```text
Phase 1 -> Phase 2 -> US1/US2/US3
US1 -> US2
US2 -> US3
US2 -> US4
US2 -> US5
US2 -> US6
Backend API slices -> Frontend module
All backend/frontend slices -> Docs and final verification
```

## Parallel Opportunities

- T002-T005 can run in parallel.
- T013-T015 can run in parallel.
- T020-T022 can run in parallel.
- T027-T028 can run in parallel.
- T034-T035 can run in parallel.
- T040-T044 can run in parallel.
- T050-T051 can run in parallel.
- T056-T057 can run in parallel.
- T062-T064 can run in parallel.

## Implementation Strategy

Deliver in professional PR slices:

1. Schema/ORM foundation.
2. Backend readiness and session API.
3. Dry-run worker.
4. Account integration and operation policy.
5. Frontend module.
6. Presets, docs, and final verification.

Each slice must be independently testable and must not introduce live Telegram behavior.
