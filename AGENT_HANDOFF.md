# StylistTG Agent Handoff

This is the current project memory for the next engineer or AI agent.
It intentionally describes the codebase as it works now, not the original MVP scope.

## Project

- Name: `StylistTG`
- Root: `C:\Users\user\Documents\workspace-codex\StylistTG`
- Purpose: local Telegram account/profile automation tool powered by TDLib.
- Primary UX: account list -> profile editor -> create execution task -> watch step-by-step progress.
- User preference: answers should be short and practical; UI should be minimal, clean, and not visually bulky.

## Current Product Scope

Implemented or actively wired:

- Telegram OTP auth and 2FA password handling.
- Single-account profile editing.
- Batch account addition/auth flow.
- Profile fields:
  - first name
  - last name
  - username
  - bio
  - profile photo
- Profile music upload/apply/remove flow.
- Story draft upload and posting flow.
- Display of active story posts known to the app.
- Deleting known active story posts through the app.
- Runtime diagnostics, live readiness, settings, cooldown policy.
- Account Safety & Readiness Engine: health/risk/capabilities, read-only validity checks, operation cooldowns, safety overrides.
- Per-account proxy assignment/status, technical proxy connectivity checks, and TDLib read-only proxy verification in TDLib live mode.
- Operation logs: account-level recent history, debug history, and global `/operations` journal.
- SaaS backend foundation and production-hardening:
  - workspace/user/member ownership model;
  - local vs Supabase JWT auth modes;
  - production guard blocking unsafe local auth in cloud/prod;
  - JWKS cache/rotation for Supabase JWT verification;
  - GitHub Actions CI for backend/frontend safe validation.
- Storage abstraction:
  - application assets go through a storage service;
  - local adapter is active for dev/test;
  - real S3/R2/MinIO-compatible adapter exists for application assets;
  - asset rows keep storage metadata and legacy source/normalized paths for compatibility;
  - signed URLs are only for non-sensitive application assets;
  - TDLib session storage remains separate, backend-only, and local.
- Cloud dev/staging bootstrap tooling:
  - `.env.cloud.example` is the cloud env contract;
  - `python -m app.scripts.cloud_config_check` validates Neon/Supabase/R2/Redis/TDLib boundaries without printing secrets;
  - `python -m app.scripts.cloud_smoke` orchestrates safe read-only/dry-run smoke checks;
  - `python -m app.scripts.staging_smoke` checks deployed `/health` and `/ready`, then runs safe cloud config, Neon, Supabase, Redis, and optional storage smoke checks;
  - object storage writes require `--allow-write-cloud`;
  - migrations require `--allow-migrations`;
  - production smoke requires explicit `--allow-production`.
- Frontend monorepo/SaaS foundation:
  - npm workspaces and Turborepo are active at the repo root;
  - dashboard app lives in `apps/dashboard`;
  - shared packages live under `packages/api-client`, `packages/ui`, and `packages/config`;
  - `packages/api-client` generates TypeScript OpenAPI types from FastAPI with `npm run generate:api`;
  - `npm run check:api` verifies generated OpenAPI artifacts are current and is part of frontend CI;
  - dashboard API calls are routed through `@stylisttg/api-client`; `apps/dashboard/src/lib/api.ts` is a compatibility wrapper for existing imports;
  - auth and auth-batch modules use `@stylisttg/api-client` for network transport while keeping local UI parsing/state helpers;
  - SaaS shell has Accounts, Health Center, Jobs, Proxy Center, Settings, and future Billing zones;
  - Health Center shows liveness/readiness, dependency status, backend environment/auth/storage posture, and backend account risk aggregates;
  - `/diagnostics/frontend-summary` exposes safe metadata only and must not return raw DB/Redis/S3/JWT/TDLib session values;
  - Account Risk is a backend deterministic app-known readiness score, not a Telegram anti-ban guarantee;
  - Playwright browser QA lives in `apps/dashboard/e2e` and uses mocked API data with screenshots stored in ignored artifacts;
  - TanStack Table/Form/Virtual foundations are present, read-only or preview-only;
  - backend remains at `backend/` to preserve `backend/Dockerfile` staging deploys.
- Staging backend/worker deploy readiness:
  - backend Docker packaging lives in `backend/Dockerfile`;
  - Render-oriented service template lives in `render.yaml`;
  - staging deploy runbook lives in `docs/runbooks/staging-backend-worker-deploy.md`;
  - web command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`;
  - worker command is `python -m rq.cli worker profile_jobs auth_jobs --url $REDIS_URL --worker-class rq.SimpleWorker`;
  - migration command is `python -m alembic upgrade head`;
  - keep `PROFILE_EXECUTION_ADAPTER=mock` until a separate TDLib runtime image/volume PR.
- SaaS backend foundation: runtime/direct DB URL split, local workspace bootstrap, AuthContext abstraction, identity/workspace/audit/limits models, and tenant-scoped core API access.
- Polling-first job progress UI with grouped story mini-pipelines.

Still limited or intentionally cautious:

- No WebSocket/SSE; frontend polling is the contract.
- Live TDLib actions against real Telegram should be treated as sensitive.
- Story publishing/deleting depends on Telegram limits and TDLib behavior.
- Full import of arbitrary existing Telegram profile state is not guaranteed for every field.
- Docker remains optional; this Windows workstation prefers portable Memurai for Redis.

## Stack

- Frontend: React 19, TypeScript, Vite, Tailwind CSS v4, shadcn-style components, lucide-react.
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic settings.
- Queue: Redis + RQ.
- DB: PostgreSQL by default; tests may use isolated DB fixtures.
- SaaS DB target: Neon Postgres. Runtime uses pooled DB URL; migrations/admin use direct DB URL.
- SaaS auth target: Supabase Auth JWT. Supabase is not a data access layer.
- Telegram engine: TDLib via `tdjson.dll`.
- File storage: storage abstraction over local disk or S3/R2/MinIO-compatible object storage for application assets; TDLib sessions are separate backend-only storage.
- Execution model: API creates a DB job, RQ worker executes it, frontend polls status.

## Agent Startup Expectations

- Activate the current project with Serena when available.
- Use Superpowers workflows when the task fits.
- Use `karpathy-guidelines`: clarify assumptions, keep changes surgical, verify before claiming completion.
- For planning, prefer Spec Kit; use Superpowers brainstorming first for unclear product/UI-heavy work.
- Do not modify application source before the planning path is agreed unless the change is trivial/obvious.
- For SaaS backend work, keep FastAPI as the only data access layer. Frontend must never access Neon/Supabase tables directly.

## Safety Rules

OK without asking:

- Read files.
- Edit local project files for the requested task.
- Run frontend/backend tests, lint, typecheck, build.
- Improve UI or docs within scope.

Ask first:

- Live TDLib calls against a real Telegram account.
- `npm install` / `pip install`.
- Deleting important files.
- Git push / PR / commit if not explicitly requested.
- Changing or printing secrets from `.env` / `backend/.env`.

Never:

- Commit secrets.
- Reset or revert user changes.
- Assume Redis/worker are running.

## Local Runtime

Recommended one-command launcher on this Windows workstation:

```powershell
.\scripts\start-dev.ps1
```

It is intended to:

- start Memurai Redis from `C:\Tools\Memurai`;
- run Alembic migrations;
- start FastAPI backend;
- start separate RQ workers for `profile_jobs` and `auth_jobs`;
- start Vite frontend at `http://localhost:5173`.

Manual frontend:

```powershell
npm run dev
npm test
npm run lint
npm run build
```

Manual backend:

```powershell
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
python -m pytest -q
python -m ruff check .
```

Manual worker:

```powershell
cd backend
python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
```

Redis note:

- Prefer portable Memurai at `C:\Tools\Memurai`.
- Do not use WSL Redis for this project; it has caused localhost/port instability.
- Keep `docker-compose.yml`; it remains the portable Docker option for PostgreSQL + Redis.

## Readiness and Diagnostics

- `/health`: process liveness; API can be alive while Redis is down.
- `/ready`: returns OK only when DB and Redis are OK.
- `/diagnostics/runtime`: structured runtime diagnostics.
- `/diagnostics/live-preflight`: live readiness checks.
- Settings UI shows system/runtime readiness and should use Russian labels/tooltips.
- Production SaaS deployment runbook: `docs/runbooks/saas-production-deployment.md`.
- API error model migration note: `docs/architecture/api-error-model.md`.

Important operational point:

- If Redis or RQ worker is down, jobs can stay queued or readiness can be degraded.
- That is infrastructure state, not necessarily a frontend bug.

## Backend Layout

Entry point:

- `backend/app/main.py`

Routers:

- `backend/app/api/auth.py` - single-account auth runtime mode, OTP, 2FA.
- `backend/app/api/auth_batches.py` - batch account auth.
- `backend/app/api/accounts.py` - accounts list, account runtime, jobs.
- `backend/app/api/dashboard.py` - aggregated profile dashboard.
- `backend/app/api/account_update.py` - current expanded account update workflow.
- `backend/app/api/jobs.py` - older profile job endpoints still present.
- `backend/app/api/assets.py` - profile photo/audio/story asset uploads and content.
- `backend/app/api/story_drafts.py` - story drafts.
- `backend/app/api/story_posts.py` - active story post deletion.
- `backend/app/api/story_capabilities.py` - story capability/readiness metadata.
- `backend/app/api/settings.py` - execution policy settings.
- `backend/app/api/diagnostics.py` - runtime/live diagnostics.
- `backend/app/api/operation_logs.py` - global operation log journal.

Core services:

- `backend/app/services/auth.py`
- `backend/app/services/auth_batches.py`
- `backend/app/services/auth_batch_dispatcher.py`
- `backend/app/services/auth_batch_tdlib.py`
- `backend/app/services/accounts.py`
- `backend/app/services/dashboard.py`
- `backend/app/services/account_update_jobs.py`
- `backend/app/services/account_update_plan.py`
- `backend/app/services/jobs.py`
- `backend/app/services/profile_sync.py`
- `backend/app/services/profile_audio_state.py`
- `backend/app/services/profile_photo_state.py`
- `backend/app/services/story_drafts.py`
- `backend/app/services/story_posts.py`
- `backend/app/services/story_capabilities.py`
- `backend/app/services/runtime_diagnostics.py`
- `backend/app/services/stale_jobs.py`
- `backend/app/services/account_safety.py`
- `backend/app/services/account_validity.py`
- `backend/app/services/account_cooldowns.py`
- `backend/app/services/account_safety_overrides.py`
- `backend/app/services/operation_logs.py`
- `backend/app/services/proxy_accounts.py`
- `backend/app/services/proxy_checks.py`
- `backend/app/services/tdlib_proxy.py`
- `backend/app/services/auth_context.py`
- `backend/app/services/workspaces.py`
- `backend/app/services/tenant_scope.py`
- `backend/app/services/audit_logs.py`
- `backend/app/services/limits.py`
- `backend/app/services/supabase_jwt.py`

Adapters/workers:

- `backend/app/adapters/tdlib_auth.py`
- `backend/app/adapters/tdlib_profile_execution.py`
- `backend/app/adapters/profile_execution.py` - mock fallback.
- `backend/app/workers/profile_jobs.py`
- `backend/app/workers/account_update_jobs.py`
- `backend/app/workers/auth_batch_jobs.py`
- `backend/app/tdlib_job.py`

## Backend Data Model

Main SQLAlchemy models live in `backend/app/models.py`:

- `Account`
- `AccountRuntimeState`
- `AccountAuthAttempt`
- `AuthBatch`
- `AuthBatchItem`
- `AuthAttempt`
- `AuthBatchEvent`
- `IdempotencyKey`
- `AccountProfileState`
- `AccountProfileAudioState`
- `AccountStoryPost`
- `AccountStoryDraft`
- `Job`
- `JobStepResult`
- `Asset`
- `AccountSafetySnapshot`
- `AccountValidityCheckRun`
- `AccountOperationCooldown`
- `AccountSafetyOverride`
- `AccountOperationLog`
- `AccountProxy`

Important source-of-truth rule:

- `account_profile_state` is the source of truth for current text profile.
- `account_profile_audio_state` stores known profile music state.
- `account_story_post` stores active story posts known to the app.
- `job.plan_json_snapshot` is plan truth.
- `job_step_result` is execution truth.
- Parent worker writes final truth to DB; child subprocess should not be the final DB writer.
- `account_proxy.password_encrypted` must never be returned to the frontend.
- `account_operation_log.metadata_json` must not contain secrets; use `operation_logs.log_operation()` so sensitive keys are sanitized.

## Account Safety, Proxy, and Operation Logs

Current safety endpoints:

- `GET /api/accounts/safety-summary`
- `GET /api/accounts/{account_id}/safety`
- `POST /api/accounts/{account_id}/validity-check`
- `GET /api/accounts/{account_id}/validity-checks`
- `POST /api/accounts/{account_id}/safety-overrides`
- `POST /api/accounts/safety-batch-preview`

Proxy endpoints:

- `GET /api/accounts/proxy-summary`
- `GET /api/accounts/{account_id}/proxy`
- `PUT /api/accounts/{account_id}/proxy`
- `DELETE /api/accounts/{account_id}/proxy`
- `POST /api/accounts/{account_id}/proxy/check`

Operation log endpoints:

- `GET /api/accounts/{account_id}/operation-logs`
- `GET /api/operation-logs`

Important proxy rules:

- Proxy is network routing/diagnostics, not anti-ban wording.
- Proxy check is a technical connectivity check and does not perform Telegram profile writes.
- Saved per-account proxy settings are applied to TDLib auth/runtime/profile/sync/read-only validity paths before Telegram queries.
- In TDLib live mode, `POST /api/accounts/{account_id}/proxy/check` first performs TCP diagnostics and then a read-only TDLib validity check through the saved proxy.
- Proxy status distinguishes TCP-only availability from TDLib verification:
  - `tcp_working`: TCP connection to proxy works, Telegram through proxy was not verified.
  - `tdlib_working`: read-only TDLib check through proxy succeeded.
  - `tdlib_unverified`: TCP works but account is not ready for Telegram verification, for example login is needed.
  - `failed`: TCP proxy check failed.
  - `tdlib_failed`: TDLib/proxy runtime verification failed.
- Proxy passwords are encrypted at rest and never returned in API DTOs, operation log metadata, stderr summaries, or frontend state.
- Proxy passwords require `PROXY_CREDENTIALS_ENCRYPTION_KEY` in local `.env` / `backend/.env`.
- `.env` and `backend/.env` are ignored and must never be committed or printed.
- `cryptography` is a backend dependency for Fernet encryption.

## Current Main Workflow: Account Update

The expanded workflow is preferred for profile/audio/story updates:

- Preview: `POST /api/account-update/preview`
- Create job: `POST /api/account-update/jobs`

Frontend wrappers:

- `previewAccountUpdateJob` in `src/lib/api.ts`
- `createAccountUpdateJob` in `src/lib/api.ts`

Backend:

- `backend/app/api/account_update.py`
- `backend/app/services/account_update_jobs.py`
- `backend/app/services/account_update_plan.py`

Desired state shape:

- `profile.name`
- `profile.bio`
- `profile.username`
- `profile.photo_asset_id`
- `profile_audio.action`: `keep`, `add`, `remove`
- `profile_audio.audio_asset_id`
- `stories[]`

Possible plan steps:

- `set_name`
- `set_bio`
- `set_username`
- `set_profile_photo`
- `upload_profile_audio`
- `add_profile_audio`
- `remove_profile_audio`
- `story_N_validate_capabilities`
- `story_N_prepare_media`
- `story_N_post`

Frontend groups story steps into one visible row per story with child steps:

- Проверка
- Подготовка
- Публикация

Relevant frontend logic:

- `src/lib/jobs.ts`
- `src/components/dashboard/jobs/JobPanels.tsx`

## Legacy Profile Job API

Still present:

- `POST /api/jobs/profile/preview`
- `POST /api/jobs/profile`

Use the account-update workflow for new profile/audio/story work unless there is a specific reason to use the legacy endpoint.

## Frontend Layout

Main orchestrator:

- `src/App.tsx`
- `src/hooks/useAccountSelectionFlow.ts`
- `src/hooks/useAuthBootstrap.ts`
- `src/hooks/useDashboardActions.ts`
- `src/hooks/useDashboardPresentation.ts`
- `src/hooks/useTerminalJobRefresh.ts`

Auth:

- `src/hooks/useAuthFlow.ts`
- `src/components/auth/AuthScreen.tsx`
- `src/components/auth/AuthPhoneStep.tsx`
- `src/components/auth/AuthCodeStep.tsx`
- `src/components/auth/AuthPasswordStep.tsx`
- `src/components/auth/AuthStatusBlock.tsx`

Batch auth:

- `src/components/auth/BulkAuthScreen.tsx`
- `src/lib/authBatches.ts`
- `src/lib/authBatches.test.ts`

Accounts/settings:

- `src/components/dashboard/accounts/AccountList.tsx`
- `src/components/dashboard/accounts/SettingsPanel.tsx`
- `src/lib/accounts.ts`
- `src/lib/settings.ts`
- `src/lib/diagnostics.ts`

Dashboard/profile editor:

- `src/hooks/useDashboard.ts`
- `src/hooks/useProfileDraft.ts`
- `src/lib/dashboard.ts`
- `src/components/dashboard/DashboardHeader.tsx`
- `src/components/dashboard/DashboardActionBar.tsx`
- `src/components/dashboard/profile/ProfilePanels.tsx`
- `src/components/dashboard/profile/AvatarBlock.tsx`
- `src/components/dashboard/profile/MusicBlock.tsx`
- `src/components/dashboard/profile/StoriesBlock.tsx`

API client/types:

- `src/lib/api.ts`
- `src/lib/http.ts`
- `src/lib/uiLabels.ts`

Server-state/query layer:

- `src/lib/queryClient.ts` - app-wide TanStack Query defaults.
- `src/lib/queries.ts` - canonical query keys and query options.
- `src/hooks/queries/useAccountsQueries.ts`
- `src/hooks/queries/useSettingsQueries.ts`
- `src/hooks/queries/useDashboardMutations.ts`
- `src/hooks/useDashboardJobPolling.ts`

Important query rules:

- Reuse `queryKeys` and query option helpers; do not invent ad-hoc string keys in components.
- Account-scoped dashboard data must live under `queryKeys.dashboard.account(accountId)` so account cleanup removes all related cached state.
- `dashboardBundleQueryOptions(accountId)` is the current fast editor bootstrap path.
- Granular options (`dashboardProfileQueryOptions`, `storyDraftsQueryOptions`, `storyCapabilitiesQueryOptions`, jobs/job steps) are available for future route/page splits.
- Use targeted cache updates/invalidation after mutations. Avoid global query invalidation unless a change truly affects the whole app.
- Proxy and operation-log queries live in `src/lib/queries.ts`; do not create ad-hoc keys for them in components.

## Frontend Navigation

TanStack Router is the canonical frontend routing layer. Route tree:

- `/` for accounts
- `/settings`
- `/auth/batch`
- `/operations`
- `/accounts/$accountId`
- `/accounts/$accountId/profile`
- `/accounts/$accountId/jobs`
- `/accounts/$accountId/stories`
- `/accounts/$accountId/music`
- `/accounts/$accountId/debug`

Helper:

- `src/lib/routes.ts`
- `src/router.tsx`
- `src/routes/AccountsRoute.tsx`
- `src/routes/AuthBatchRoute.tsx`
- `src/routes/OperationsRoute.tsx`
- `src/routes/AccountWorkspaceRoute.tsx`
- `src/routes/pending.tsx`
- `src/routes/error.tsx`

Rules:

- Refresh on settings should stay on settings.
- Refresh on batch auth should stay on batch auth.
- Browser back/forward is owned by TanStack Router, not manual `popstate` listeners.
- Use `src/lib/routes.ts` for route strings; do not add ad-hoc route strings in components.
- Route-level code splitting is done through TanStack Router `lazyRouteComponent`.
- Split at product route boundaries first: accounts/settings, batch auth, and account workspace.
- Keep account workspace loaders data-first: `authState` and `dashboardBundle` should be ready before the editor renders.
- Use the small route pending fallback for cold loads only; warm cached navigation should render from TanStack Query cache without a full skeleton flash.
- Route loader/component failures use the TanStack Router error component with user-facing Russian text and hidden technical details.
- Old query URLs are compatibility redirects only:
  - `/?view=settings` -> `/settings`
  - `/?view=auth-batch` -> `/auth/batch`
  - `/?account_id=...` -> `/accounts/...`
- Do not reintroduce query-param/phase routing as the primary navigation model.

## Batch Account Addition

Current UI goal:

- One entry point: `Добавить аккаунты`.
- Same form supports one number or many numbers.
- No separate primary single-account add button in the account list.

Phone input behavior:

- Sanitizes pasted input.
- Auto-adds `+`.
- Caps phone digits to 15.
- Supports labels after comma: `79991234567, Марина`.
- Stores cleaned draft in `localStorage`.
- Shows compact preview and validation summary.

Actions:

- `Уникализировать`
- `Только новые`
- `Очистить всё`
- `Проверить`
- Primary button:
  - 1 parsed phone: `Добавить аккаунт`
  - 2+ parsed phones: `Добавить аккаунты`

Test DC:

- It is a dev/advanced mode.
- Ordinary Telegram accounts do not authorize there.
- Disabling Test DC inside batch form must stay on `/auth/batch`, not redirect to old single auth UI.

## Profile Draft Persistence

The dashboard form draft is persisted per account in `localStorage`.

Reason:

- If a job fails or the page refreshes, the user should not lose entered name, username, bio, photo/audio/story drafts.

Relevant logic:

- `src/lib/dashboard.ts`
- `src/hooks/useProfileDraft.ts`

Only clear draft automatically after a fully completed job:

- `shouldResetDraftAfterJobState('completed') === true`

## Profile Music

Frontend:

- `src/components/dashboard/profile/MusicBlock.tsx`

Backend:

- `backend/app/services/profile_audio_state.py`
- `backend/app/services/account_update_plan.py`
- `backend/app/adapters/tdlib_profile_execution.py`

Asset upload:

- `POST /api/assets/profile-audio`

Supported execution formats:

- MP3
- M4A

Known localized errors:

- `PROFILE_AUDIO_UPLOAD_NOT_COMPLETED`
- `PROFILE_AUDIO_MESSAGE_SEND_FAILED`
- `PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT`
- `PROFILE_AUDIO_FILE_ID_MISSING`
- `PROFILE_AUDIO_UNSUPPORTED_FORMAT`
- `TDLIB_UNSUPPORTED_UPLOAD_FILE_METHOD`

Important nuance:

- Telegram/TDLib may require upload through supported TDLib file APIs.
- Do not fake success; the job UI should show the real failed step.

## Stories

Frontend:

- `src/components/dashboard/profile/StoriesBlock.tsx`

Backend:

- `backend/app/api/story_drafts.py`
- `backend/app/api/story_posts.py`
- `backend/app/api/story_capabilities.py`
- `backend/app/services/story_drafts.py`
- `backend/app/services/story_posts.py`
- `backend/app/services/story_capabilities.py`

Assets:

- `POST /api/assets/story-image`
- `POST /api/assets/story-video`

Current UX:

- User can add story draft from image/video.
- User can set caption/privacy.
- User can create account update job that publishes stories.
- Known active stories are displayed under "Сейчас в профиле".
- User can delete known active stories from UI.

Telegram limitations:

- Normal accounts have active/weekly story limits.
- Premium may have higher limits, but do not hardcode exact external limits without verifying.

Localized current labels:

- `CAN_POST_STORY_ACTIVE_STORY_LIMIT_EXCEEDED`:
  `Лимит активных историй для обычного аккаунта. Удалите одну историю, дождитесь окончания или используйте Premium с повышенным лимитом`
- `CAN_POST_STORY_WEEKLY_LIMIT_EXCEEDED`:
  `Достигнут недельный лимит историй. Приобретите Premium`

Config:

- `stories_enabled = True`
- `stories_tdlib_live_enabled = False` by default.

If live story publishing is blocked, check config before assuming UI bug.

## Account List and Settings

Account list:

- `src/components/dashboard/accounts/AccountList.tsx`
- Shows accounts, avatars if known, status, filters/search.
- Primary add action should go to batch auth.

Settings:

- `src/components/dashboard/accounts/SettingsPanel.tsx`
- Shows system readiness, live readiness, execution policy, Test DC advanced setting.
- Labels should be Russian.
- Technical readiness items should have simple tooltips.

Execution policy:

- `GET /api/settings/execution-policy`
- `PATCH /api/settings/execution-policy`

## Error Labels

UI label mapping lives in:

- `src/lib/uiLabels.ts`

Add user-facing translations there when backend exposes technical codes.

Examples:

- `NETWORK_ERROR` -> `Нет связи с backend`
- `QUEUE_UNAVAILABLE` -> `Очередь задач недоступна`
- `USERNAME_PURCHASE_AVAILABLE` -> `Юзернейм доступен только через покупку`
- `PROFILE_AUDIO_FILE_ID_MISSING` -> `Telegram не вернул файл музыки`
- `CAN_POST_STORY_WEEKLY_LIMIT_EXCEEDED` -> `Достигнут недельный лимит историй. Приобретите Premium`

## Job Progress UI

Relevant files:

- `src/components/dashboard/jobs/JobPanels.tsx`
- `src/lib/jobs.ts`

Current UX direction:

- Minimal floating/absolute "План и выполнение" panel.
- It should not push main profile form blocks.
- It can collapse to a compact button.
- Header should not show duplicated full error block; errors should primarily appear in the failed step.
- Story groups should be one row with mini-pipeline child steps.

## Known Operational/Design Nuances

- Some Telegram errors are real account/platform limits, not app bugs.
- Username can fail because Telegram sells/reserves some usernames.
- Story limits can block publishing even when app logic is correct.
- Redis/worker readiness is separate from frontend/backend process liveness.
- Profile photo/avatar sync from Telegram is limited to app-known assets unless a dedicated download sync is implemented.
- Full "real sync everything from Telegram" is complex; check TDLib capabilities and current services before promising it.
- Do not use browser native `confirm()` for important app actions; use app-styled modal UI.

## Current Test Status

Recently verified after frontend UI changes:

- `npm test` passed.
- `npm run lint` passed.
- `npm run build` passed.

Earlier backend checks have passed during this workstream:

- `python -m pytest -q`
- `python -m ruff check .`

Before claiming a fix is done, rerun the relevant subset and preferably the full frontend checks for UI changes.

## Practical First Steps for a New Agent

1. Read `AGENTS.md`.
2. Activate project in Serena.
3. Read this `AGENT_HANDOFF.md`.
4. Check current app state with `npm test`, `npm run build` only if changing frontend.
5. For backend work, inspect the exact router/service/test around the requested behavior.
6. For Telegram live behavior, ask before making live TDLib calls.
7. Keep changes small and localized.
