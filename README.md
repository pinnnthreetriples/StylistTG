# StylistTG

[![CI](https://github.com/pinnnthreetriples/StylistTG/actions/workflows/ci.yml/badge.svg)](https://github.com/pinnnthreetriples/StylistTG/actions/workflows/ci.yml)

Local Telegram account/profile automation tool powered by TDLib.

The app currently focuses on:

- adding and authorizing accounts, including batch addition;
- editing profile name, username, bio, avatar, profile music, and stories;
- creating queued account update jobs and showing step-by-step execution progress;
- local runtime/readiness diagnostics for Redis, workers, TDLib, DB, storage, and live checks;
- account preparation / warmup foundations with dry-run, shadow, and gated live modes.

## Stack

- TDLib for account runtime operations.
- FastAPI backend.
- RQ + Redis worker layer.
- PostgreSQL as the source of truth.
- React + TypeScript + Vite dashboard.
- Shared product UI primitives in `@stylisttg/ui`.
- Generated API client in `@stylisttg/api-client`.
- Local asset storage for development and S3/R2/MinIO-compatible object storage for production assets.

## Current Limits

- No WebSocket/SSE; frontend is polling-first.
- Live TDLib execution is disabled by default and must stay explicitly gated.
- Workspace Safety Policy is temporarily neutralized while `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED=True`; see `.mex/status/current.md` and `docs/runbooks/safety-rollout.md`.
- Story publishing/deletion depends on account limits and TDLib capabilities.
- Automatic asset migration from local storage to S3/R2/MinIO is not implemented.

## Account Safety Pipeline

StylistTG has a safety-pipeline foundation: WorkspaceSafetyPolicy, GGR Calculator, AccountQuarantine, AccountStatusMonitor, CrossModuleLoadTracker, and AccountSafetyGate. Current status matters: Workspace Safety Policy is temporarily neutralized by developer decision, so do not describe the full policy layer as active until `.mex/status/current.md` is superseded.

Details:

- `.mex/status/current.md`
- `docs/modules/account-safety-pipeline.md`
- `docs/runbooks/safety-rollout.md`

## Local Development

For a step-by-step setup of Python and Node dependencies, security scanners, and optional system tools, see `docs/runbooks/dev-environment-setup.md`.

Recommended one-command launcher on Windows:

```powershell
.\scripts\start-dev.ps1
```

It starts Redis-compatible Memurai from `C:\Tools\Memurai`, runs migrations, starts the FastAPI backend on port `8002`, starts separate RQ workers, and starts Vite on port `5173`. It does not open a browser by default; pass `-OpenBrowser` to launch `http://localhost:5173`.

Frontend commands:

```powershell
npm install
npm run dashboard:dev
npm run generate:api
npm run check:api
npm run lint
npm test
npm run coverage
npm run build
npm run qa:browser
```

Backend commands:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8002
```

Infrastructure:

```powershell
docker compose up -d postgres redis
```

Worker examples:

```powershell
cd backend
python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
python -m app.workers.run_worker --queues warmup_jobs
python -m app.workers.run_worker --queues warmup_dispatch_jobs
python -m app.workers.run_worker --queues neuro_comment_jobs --role neuro_comment_worker
```

Dashboard local development uses backend port `8002`. Live-validation helper scripts that call `scripts/start_backend.ps1` may use `8000`; use the actual startup output and set `$ApiBaseUrl` before copying examples.

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

Readiness semantics:

- `/health` returns `200` when the API process is alive.
- `/ready` returns `200` only when both `database=ok` and `redis=ok`.
- `/ready` returns `503` when either database or Redis is down.
- Diagnostics endpoints return structured troubleshooting payloads and must not expose DB URLs, Redis URLs, S3 credentials, JWTs, or TDLib session paths.

## Project Memory

```powershell
npm run memory:check
npm run memory:sync:dry-run
```

- Start from `AGENTS.md`, then read `.mex/ROUTER.md` and `.mex/status/current.md`.
- `.mex/status/` stores temporary current state.
- `.mex/context/` stores compact stable project facts.
- `.mex/patterns/` stores repeatable task workflows.
- Do not run `npm run memory:sync` without explicit approval.

## Documentation Map

- Frontend/backend contract: `docs/api/frontend.md`.
- Architecture docs: `docs/architecture/`.
- Account lifecycle and production-plane docs: `docs/architecture/account-lifecycle.md`, `docs/architecture/production-execution-plane.md`.
- Account safety: `docs/modules/account-safety-pipeline.md`, `docs/runbooks/safety-rollout.md`.
- Live validation: `docs/runbooks/live-validation.md`.
- Account import/auth: `docs/runbooks/account-import.md`, `docs/runbooks/telegram-auth-flow.md`.
- Cloud/staging deploy: `docs/runbooks/cloud-dev-staging-bootstrap.md`, `docs/runbooks/staging-backend-worker-deploy.md`.
- Required CI/branch-protection checks: `docs/quality/REQUIRED_CHECKS.md`.
- Agent project-board workflow: `docs/agents/project-board.md`.

## Safety Notes

Telegram codes, 2FA passwords, API hashes, TDLib paths, session material, cloud env files, proxy passwords, logs, and artifacts must never be logged, returned in API responses, committed, or copied into agent memory.

## CI and Quality

Branch-protection and required checks are documented in `docs/quality/REQUIRED_CHECKS.md`; do not duplicate the current required-check list here. CI includes backend checks, frontend checks, OpenAPI drift, browser QA, test quality, security scanning, and container/filesystem scanning according to that document.
