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
- Local disk file storage for the first stage.
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

Still intentionally limited:

- No WebSocket/SSE; frontend is polling-first.
- Live Telegram calls should be treated carefully.
- Story publishing/deletion depends on Telegram account limits and TDLib capabilities.
- S3 or MinIO.
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
npm run dev
```

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
```

Use separate workers in normal development: `profile_jobs` executes profile/account-update work, `auth_jobs` executes batch-auth work. Diagnostics report both statuses separately.

Diagnostics:

```powershell
cd backend
python -m app.tools.live_preflight
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/diagnostics/live-preflight
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/diagnostics/runtime
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/ready
```

Readiness semantics:

- `/health` returns `200` when the API process is alive.
- `/ready` returns `200` only when both `database=ok` and `redis=ok`.
- `/ready` returns `503` when either database or redis is down.
- `/diagnostics/runtime` and `/diagnostics/live-preflight` always return structured payloads for troubleshooting.

OTP auth flow:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/otp/start -ContentType 'application/json' -Body '{"phone_number":"+15550102000"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/otp/confirm -ContentType 'application/json' -Body '{"account_id":"<account-id>","code":"12345"}'
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/<account-id>/auth-state
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/<account-id>/refresh-runtime
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/<account-id>/runtime-diagnostics
```

TDLib configuration:

```powershell
$env:TDLIB_API_ID="<your api id>"
$env:TDLIB_API_HASH="<your api hash>"
$env:TDLIB_DATABASE_ROOT="backend/tdlib/database"
$env:TDLIB_FILES_ROOT="backend/tdlib/files"
$env:TDLIB_SHARED_LIBRARY_PATH="C:\\path\\to\\tdjson.dll"
$env:PROFILE_EXECUTION_ADAPTER="tdlib"
```

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

CI:

- `.github/workflows/ci.yml` runs backend checks against real PostgreSQL and Redis services.
- Backend CI runs Alembic heads, upgrade head, migration smoke, ruff, pytest, and compileall.
- Frontend CI runs `npm ci`, lint, tests, and build.
- Private repo on the current GitHub plan cannot enforce branch protection/rulesets.
  Until GitHub Pro or a public repo is available, follow
  [docs/runbooks/git-workflow-without-branch-protection.md](docs/runbooks/git-workflow-without-branch-protection.md)
  manually.

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
npm run build
cd backend
python -m ruff check .
python -m pytest
python -m pytest tests/test_tdlib_integration_contract.py -m integration
python -m pytest tests/test_tdlib_profile_live_contract.py -m integration
python -m pytest -m live
python -m compileall app
```
