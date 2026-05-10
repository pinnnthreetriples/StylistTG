# Workers Production Plane Runbook

## Goal

Run queue-specific workers with explicit safety gates, locks, rate limits, cooldowns, and bounded retry policy.

## Queues

```text
auth_jobs
profile_jobs
media_jobs
story_jobs
account_lifecycle_jobs
maintenance_jobs
scheduler_jobs
warmup_jobs
warmup_dispatch_jobs
```

## Commands

Existing compatibility worker:

```powershell
cd backend
python -m app.workers.run_worker --queues profile_jobs,auth_jobs
```

Queue-specific launcher:

```powershell
cd backend
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
python -m app.workers.run_worker --queues warmup_jobs
python -m app.workers.run_worker --queues warmup_dispatch_jobs
```

Unknown queues are rejected.

Auth-session jobs use the `auth_jobs` queue. They are allowed only for Telegram authorization/reauthorization state transitions and must not run profile/story/music mutations.

Warmup dry-run sessions use `warmup_jobs`. Shadow/live micro-session dispatch uses `warmup_dispatch_jobs`; live modes require explicit warmup feature gates and operator approval before touching real Telegram accounts.

Future TDLib live auth worker command, after the TDLib runtime image and isolated
volume mounts are validated:

```powershell
cd backend
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json
python -m app.workers.run_worker --queues auth_jobs
```

Keep `TDLIB_LIVE_ENABLED=false` until controlled live auth validation is
explicitly approved. `profile_jobs` remains mock-safe unless a later PR enables
live profile execution behind separate gates.

## Diagnostics

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/workers/queues
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/workers/diagnostics
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/jobs/policies
```

Use the actual API port from the startup script. `scripts/start_backend.ps1` defaults to `8000`; `scripts/start-dev.ps1` starts the dashboard stack with backend `8002`.

Diagnostics are metadata-only and must not expose Redis URL, DB URL, S3 credentials, JWTs, or TDLib session paths.

## Scheduler and Reaper

Scheduler/reaper are disabled by default:

```text
SCHEDULER_ENABLED=false
REAPER_ENABLED=false
REAPER_MODE=dry_run
```

Warmup scheduler defaults are also disabled/safe:

```text
WARMUP_WORKERS_ENABLED=false
WARMUP_SCHEDULER_ENABLED=false
WARMUP_HARD_DISABLE=false
```

Safe reports:

```powershell
cd backend
python -m app.scripts.run_scheduler
python -m app.scripts.run_reaper --mode dry_run
```

Do not use `execute_safe` until the target and max-delete guard are reviewed. Reaper must not touch TDLib sessions, account rows, account assets, or audit logs outside an approved deletion workflow.

## TDLib Live Runtime

Keep live disabled in staging:

```text
TDLIB_LIVE_ENABLED=false
PROFILE_EXECUTION_ADAPTER=mock
```

Live mode requires a separate PR for image/volume/session isolation and explicit review of locks, rate limits, risk gates, audit, and allowlisted job types.

This foundation now includes TDLib runtime detection and isolated path builders. Live auth still requires explicit `TDLIB_LIVE_ENABLED=true`, Telegram API credentials, and a loadable TDLib library; default staging keeps auth attempts safe and non-live.
