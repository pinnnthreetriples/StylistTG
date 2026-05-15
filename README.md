# StylistTG

[![CI](https://github.com/pinnnthreetriples/StylistTG/actions/workflows/ci.yml/badge.svg)](https://github.com/pinnnthreetriples/StylistTG/actions/workflows/ci.yml)

Local Telegram account/profile automation tool powered by TDLib.

The app currently focuses on:

- adding and authorizing Telegram accounts, including batch addition;
- editing profile name, username, bio, avatar, profile music, and stories;
- creating account update jobs and showing step-by-step execution progress;
- local runtime/readiness diagnostics for Redis, worker, TDLib, DB, and live checks.

## Stack

- TDLib for Telegram account operations.
- FastAPI backend.
- RQ + Redis worker layer.
- PostgreSQL as the source of truth.
- React + TypeScript + shadcn/ui frontend.
- Storage abstraction with local asset storage for development and S3/R2/MinIO-compatible object storage for production assets.
- One subprocess per queued job with a cold-start TDLib runtime.

## Current Scope

Included:

- OTP-only auth.
- 2FA password step when Telegram requests it.
- Account list and batch account addition.
- `set_name`
- `set_bio`
- `set_username`
- `set_profile_photo`
- Profile music upload/apply/remove.
- Story image/video drafts.
- Story publishing flow.
- Known active story display and deletion.
- Runtime diagnostics and execution policy settings.
- Account lifecycle security foundation: deletion preview/request, private export request, sanitized audit history, and risk-gated action checks.
- Production execution-plane foundation: queue taxonomy, queue-specific worker launcher, Redis account locks, tenant rate limits, cooldown/FLOOD_WAIT handling, retry policies, and dry-run scheduler/reaper reports.
- TDLib live runtime/auth/import foundation: tdjson detection, isolated TDLib storage paths, auth-session endpoints, reauth session endpoint, preview-first import batches, and TDLib runtime diagnostics. Live profile/story/music execution remains disabled by default.
- Account Preparation / Warmup module: readiness checks, strategy presets, workspace-scoped sessions/events/task runs, dry-run worker execution, shadow dispatch, and gated live warmup levels.

Still intentionally limited:

- No WebSocket/SSE; frontend is polling-first.
- Live Telegram calls should be treated carefully.
- Story publishing/deletion depends on Telegram account limits and TDLib capabilities.
- Automatic asset migration from local storage to S3/R2/MinIO.
- Complex preset/platform layer.

## Local Development

Recommended one-command launcher on Windows:

```powershell
.\scripts\start-dev.ps1
```

It starts Redis-compatible Memurai from `C:\Tools\Memurai`, runs migrations,
starts the FastAPI backend on port `8002`, starts separate RQ workers, and starts Vite
on port `5173`.

Frontend:

```powershell
npm install
npm run dashboard:dev
```

The frontend is an npm workspaces monorepo. Root commands still work:

```powershell
npm run generate:api
npm run check:api
npm run lint
npm test
npm run build
npm run qa:browser
```

Current frontend package layout:

- `apps/dashboard` - Vite/React dashboard app.
- `packages/api-client` - generated OpenAPI types and `openapi-fetch` helpers.
- `packages/ui` - shared UI primitives.
- `packages/config` - shared TypeScript config.

`backend/` remains at the repository root because staging API/worker deployment uses
`backend/Dockerfile`; moving it is deferred to a later deployment-aware PR.

OpenAPI drift is enforced with `npm run check:api`. Browser QA uses Playwright,
local Vite preview, and mocked API responses; screenshots/reports are ignored
under `test-results/` and `playwright-report/`.

Project memory:

```powershell
npm run memory:check
npm run memory:sync:dry-run
```

- Start from `AGENTS.md`, then read `.mex/ROUTER.md`.
- `.mex/context/` stores compact architecture, setup, workers, warmup, security, and convention memory.
- `.mex/patterns/` stores repeatable task workflows.
- Run `npm run memory:check` after memory/docs/scaffold changes or when commands, paths, ports, routes, queues, feature flags, or architecture change.
- Do not run `npm run memory:check` after every small code edit, test-only change, typo, local debug step, or purely visual tweak.
- Prefer `npm run memory:sync:dry-run`; do not run `npm run memory:sync` without explicit approval.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Infrastructure:

```powershell
docker compose up -d postgres redis
```

Windows Redis note:

- Docker Compose remains the portable full-environment option.
- This workstation uses portable Memurai at `C:\Tools\Memurai` for a lighter
  Redis-compatible local server.
- Do not use WSL Redis for this project; Windows backend/worker processes must
  reach Redis at `redis://127.0.0.1:6379/0`.

Worker:

```powershell
cd backend
python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
python -m app.workers.run_worker --queues warmup_jobs
python -m app.workers.run_worker --queues warmup_dispatch_jobs
```

Use separate workers in normal development: `profile_jobs` executes profile/account-update work, `auth_jobs` executes auth and batch-auth work, `account_lifecycle_jobs`/`maintenance_jobs` are reserved for safe lifecycle/maintenance foundations, and warmup workers are only needed when testing the warmup module. Diagnostics report the production queue taxonomy.

Diagnostics:

```powershell
cd backend
python -m app.tools.live_preflight
$ApiBaseUrl = "http://127.0.0.1:8002"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/diagnostics/live-preflight"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/diagnostics/runtime"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/diagnostics/frontend-summary"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/ready"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/workers/diagnostics"
```

`scripts/start-dev.ps1` starts the local dashboard backend on `8002`. Live-validation helper scripts that call `scripts/start_backend.ps1` default to `8000`; use the actual startup output when running those flows.

Readiness semantics:

- `/health` returns `200` when the API process is alive.
- `/ready` returns `200` only when both `database=ok` and `redis=ok`.
- `/ready` returns `503` when either database or redis is down.
- `/diagnostics/runtime` and `/diagnostics/live-preflight` always return structured payloads for troubleshooting.
- `/diagnostics/frontend-summary` returns safe dashboard metadata only; it must not expose DB URLs, Redis URLs, S3 credentials, JWTs, or TDLib session paths.

Account lifecycle and production-plane docs:

- `docs/architecture/account-lifecycle.md`
- `docs/architecture/production-execution-plane.md`
- `docs/runbooks/account-deletion.md`
- `docs/runbooks/workers-production-plane.md`
- `docs/runbooks/audit-log.md`
- `docs/architecture/tdlib-live-runtime.md`
- `docs/runbooks/tdlib-runtime.md`
- `docs/runbooks/telegram-auth-flow.md`
- `docs/runbooks/account-import.md`
- `docs/security/telegram-session-handling.md`
- `docs/runbooks/northflank-staging-readiness.md`
- `docs/runbooks/account-preparation.md`

OTP auth flow:

```powershell
$ApiBaseUrl = "http://127.0.0.1:8002"
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/auth/otp/start" -ContentType 'application/json' -Body '{"phone_number":"+15550102000"}'
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/auth/otp/confirm" -ContentType 'application/json' -Body '{"account_id":"<account-id>","code":"12345"}'
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/accounts/<account-id>/auth-state"
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/accounts/<account-id>/refresh-runtime"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/accounts/<account-id>/runtime-diagnostics"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/accounts/risk-summary"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/accounts/<account-id>/risk"
```

TDLib configuration:

```powershell
$env:TDLIB_API_ID="<your api id>"
$env:TDLIB_API_HASH="<your api hash>"
$env:TELEGRAM_API_ID="<your api id>"
$env:TELEGRAM_API_HASH="<your api hash>"
$env:TDLIB_DATABASE_ROOT="backend/tdlib/database"
$env:TDLIB_FILES_ROOT="backend/tdlib/files"
$env:TDLIB_SHARED_LIBRARY_PATH="C:\\path\\to\\tdjson.dll"
$env:TDLIB_RUNTIME_MODE="mock"
$env:TDLIB_LIVE_ENABLED="false"
$env:PROFILE_EXECUTION_ADAPTER="mock"
```

TDLib runtime smoke:

```powershell
cd backend
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check
```

Real auth/import foundation endpoints are explicit and safe-by-default:

```powershell
$ApiBaseUrl = "http://127.0.0.1:8002"
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/accounts/auth-sessions" -ContentType 'application/json' -Body '{"phone_number":"+15550102000"}'
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/account-import-batches" -ContentType 'application/json' -Body '{"source_type":"json-metadata","dry_run":true}'
```

Telegram codes, 2FA passwords, Telegram API hash, TDLib paths, and session material must never be logged, returned in API responses, or committed.

SaaS database/auth foundation:

```powershell
# Local keeps using Docker/Postgres DATABASE_URL.
$env:APP_ENV="local"
$env:DB_CONNECTION_MODE="local"
$env:DATABASE_URL="postgresql+psycopg://stylisttg:stylisttg@localhost:5432/stylisttg"
$env:AUTH_MODE="local"

# Neon runtime should use pooled connection string.
$env:APP_ENV="production"
$env:DB_CONNECTION_MODE="neon"
$env:DATABASE_RUNTIME_URL="<neon pooled connection string>"
$env:DATABASE_DIRECT_URL="<neon direct/admin connection string>"

# Auth remains local for development; production uses Supabase JWT verification.
$env:AUTH_MODE="supabase_jwt"
$env:SUPABASE_AUTH_JWKS_URL="<supabase jwks url>"
$env:SUPABASE_AUTH_ISSUER="<supabase issuer>"
$env:SUPABASE_AUTH_AUDIENCE="<supabase audience>"
$env:SUPABASE_AUTH_JWKS_CACHE_TTL_SECONDS="600"
```

Neon is the PostgreSQL provider. Supabase is used only as the auth provider; FastAPI remains the only data access layer and enforces workspace isolation.
`AUTH_MODE=local` is blocked in production/cloud mode unless `ALLOW_LOCAL_AUTH_IN_PROD=true` is explicitly set for controlled non-production testing.

Storage:

```powershell
$env:STORAGE_BACKEND="local"
$env:STORAGE_LOCAL_ROOT="backend/storage"
$env:STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS="300"
$env:TDLIB_STORAGE_BACKEND="local"
$env:TDLIB_DATABASE_ROOT="backend/tdlib/database"
$env:TDLIB_FILES_ROOT="backend/tdlib/files"
```

For production object storage set `STORAGE_BACKEND=s3` plus the `STORAGE_S3_*`
endpoint, bucket, region, access key, secret, path-style, and signed URL TTL
settings. Backblaze B2, R2, and MinIO are supported through a configurable endpoint URL.
Application assets and TDLib sessions are separate: asset rows now keep
storage metadata (`storage_backend`, source/normalized keys, sizes, content
types, checksums), while TDLib session folders remain backend-only and must
never be exposed as public assets or signed URLs.

Cloud dev/staging bootstrap:

```powershell
cd backend
python -m app.scripts.cloud_config_check
python -m app.scripts.cloud_smoke --safe-default --include-redis --include-storage
python -m app.scripts.staging_smoke --base-url https://<staging-backend> --include-storage --env-file ..\.env.cloud.local
```

Use `.env.cloud.example` as the cloud env contract. The cloud smoke tooling is
safe by default: no object write without `--allow-write-cloud`, no migrations
without `--allow-migrations`, and no production smoke without explicit approval.
See [docs/runbooks/cloud-dev-staging-bootstrap.md](docs/runbooks/cloud-dev-staging-bootstrap.md).

Staging backend/worker deploy:

- Docker image: `backend/Dockerfile`.
- Web command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Worker command: `python -m rq.cli worker profile_jobs auth_jobs --url $REDIS_URL --worker-class rq.SimpleWorker`.
- Migration command: `python -m alembic upgrade head`.
- Keep `PROFILE_EXECUTION_ADAPTER=mock` until a separate TDLib runtime image/volume plan is reviewed.
- See [docs/runbooks/staging-backend-worker-deploy.md](docs/runbooks/staging-backend-worker-deploy.md).

CI:

- `.github/workflows/ci.yml` runs backend checks against real PostgreSQL and Redis services.
- Backend CI runs Alembic heads, upgrade head, migration smoke, ruff, pip-audit,
  Pyright, pytest with coverage, compileall, and the backend Docker build.
- Frontend CI runs `npm ci`, npm audit, OpenAPI drift check, lint, tests, and build
  (`tsc -b` plus Vite). Browser QA runs for dashboard/browser-related changes.
- Test Quality runs backend Ruff format/lint, pytest coverage, coverage gate,
  test analyzer, pip-audit, soft Pyright/Schemathesis, and jscpd. Semgrep runs
  as a separate workflow. CodeQL, Secret Scan, SBOM, and Container Scan provide
  the security baseline.
- Branch protection for `main` currently requires CI status checks. PRs should also
  treat Test Quality, Semgrep, CodeQL, Secret Scan, SBOM, and Container Scan as
  merge blockers even when not marked required.

Live smoke helper:

```powershell
cd backend
python -m app.tools.live_smoke --phone-number "+15550102000"
python -m app.tools.live_smoke --account-id "<account-id>" --code "<otp-code>"
python -m app.tools.live_smoke --account-id "<account-id>" --photo-path "C:\\path\\to\\profile.jpg"
```

Operator live validation bundle:

```powershell
.\scripts\live_preflight.ps1
.\scripts\start_backend.ps1
.\scripts\start_worker.ps1
.\scripts\live_auth_flow.ps1 -PhoneNumber "+15550102000"
.\scripts\live_profile_job.ps1 -AccountId "<account-id>" -PhotoPath "C:\\path\\to\\profile.jpg"
.\scripts\capture_live_artifacts.ps1 -AccountId "<account-id>" -JobId "<job-id>"
```

Operator API token:

- `OPERATOR_API_TOKEN` is for API/reverse-proxy clients that can send `X-Operator-Token`.
- The browser UI does not store or send this token.
- Local browser development normally relies on the localhost guard instead.

Runbook:

- [docs/runbooks/live-validation.md](C:/Users/user/Documents/workspace-codex/StylistTG/docs/runbooks/live-validation.md)

Checks:

```powershell
npm run lint
npm test
npm run build
cd backend
python -m ruff check .
python -m pytest
python -m pytest tests/test_tdlib_integration_contract.py -m integration
python -m pytest tests/test_tdlib_profile_live_contract.py -m integration
python -m pytest -m live
python -m compileall app
```
