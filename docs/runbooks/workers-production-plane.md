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
```

## Commands

Existing compatibility worker:

```powershell
cd backend
python -m rq.cli worker profile_jobs auth_jobs --url $env:REDIS_URL --worker-class rq.SimpleWorker
```

Queue-specific launcher:

```powershell
cd backend
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
```

Unknown queues are rejected.

## Diagnostics

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/workers/queues
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/workers/diagnostics
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/jobs/policies
```

Diagnostics are metadata-only and must not expose Redis URL, DB URL, S3 credentials, JWTs, or TDLib session paths.

## Scheduler and Reaper

Scheduler/reaper are disabled by default:

```text
SCHEDULER_ENABLED=false
REAPER_ENABLED=false
REAPER_MODE=dry_run
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
