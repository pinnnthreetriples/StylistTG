# Deployment Processes

The backend Docker image is intentionally generic. Production deployments should run distinct process roles from that image instead of mixing API traffic and live worker execution in one process.

## Intended Process Split

| Process | Role | Notes |
| --- | --- | --- |
| API container | `api` | Serves FastAPI and module routers. It should not consume worker queues. |
| Auth worker container | `auth_worker` | Consumes `auth_jobs`; requires TDLib/session configuration when live auth execution is enabled. |
| Profile worker container | `profile_worker` | Consumes `profile_jobs`; requires TDLib/session configuration for live profile execution. |
| Warmup worker container | `warmup_worker` | Consumes `warmup_jobs`; dry-run account preparation. |
| Warmup dispatch worker container | `warmup_dispatch_worker` | Consumes `warmup_dispatch_jobs`; live-capable warmup dispatch remains gated. |
| Maintenance worker container | `maintenance_worker` | Consumes `maintenance_jobs`; no TDLib/session requirement. |
| Media worker container | `media_worker` | Consumes `media_jobs`; reserved media ownership is explicit. |
| Story worker container | `story_worker` | Consumes `story_jobs`; reserved story ownership is explicit. |
| Account lifecycle worker container | `account_lifecycle_worker` | Consumes `account_lifecycle_jobs`; reserved lifecycle ownership is explicit. |
| NeuroCommenting worker container | `neuro_comment_worker` | Consumes `neuro_comment_jobs`; safe foundation generation/manual approval support only. |
| Scheduler process | `scheduler` | Owns scheduled enqueue decisions. |
| Reaper process | `reaper` | Owns stale job reconciliation outside API replicas. |

## Worker Commands

Existing raw queue startup remains compatible:

```powershell
cd backend; python -m app.workers.run_worker --queues profile_jobs
```

Role validation can be added without changing queue names:

```powershell
cd backend; python -m app.workers.run_worker --queues profile_jobs --role profile_worker
cd backend; python -m app.workers.run_worker --queues warmup_dispatch_jobs --role warmup_dispatch_worker
cd backend; python -m app.workers.run_worker --queues maintenance_jobs --role maintenance_worker
cd backend; python -m app.workers.run_worker --queues media_jobs --role media_worker
cd backend; python -m app.workers.run_worker --queues story_jobs --role story_worker
cd backend; python -m app.workers.run_worker --queues account_lifecycle_jobs --role account_lifecycle_worker
cd backend; python -m app.workers.run_worker --queues neuro_comment_jobs --role neuro_comment_worker
```

## Operational Rules

- Do not run API replicas as live workers.
- Do not attach TDLib session storage to roles that do not require it.
- Do not add queues without runtime role metadata and tests.
- Do not treat HIGH container scan findings as merge blockers unless policy changes; CRITICAL findings block merge.
