---
name: workers
description: Redis/RQ queue taxonomy, workers, scheduler, and execution-plane rules.
triggers:
  - worker
  - queue
  - RQ
  - Redis
  - scheduler
edges:
  - .mex/context/backend.md
  - .mex/context/warmup.md
  - docs/architecture/production-execution-plane.md
last_updated: 2026-05-15
---

# Workers and Queues

## Queue taxonomy

- `auth_jobs`: Telegram auth and batch-auth execution.
- `profile_jobs`: profile/account update work.
- `media_jobs`: reserved media execution taxonomy.
- `story_jobs`: story work taxonomy.
- `account_lifecycle_jobs`: account export/deletion foundations.
- `maintenance_jobs`: safe maintenance foundations.
- `scheduler_jobs`: scheduler/reaper taxonomy.
- `warmup_jobs`: dry-run account preparation.
- `warmup_dispatch_jobs`: shadow/live warmup micro-session dispatch.

## Local workers

```powershell
cd backend; python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
cd backend; python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
cd backend; python -m app.workers.run_worker --queues warmup_jobs
cd backend; python -m app.workers.run_worker --queues warmup_dispatch_jobs
cd backend; python -m app.workers.run_worker --queues profile_jobs --role profile_worker
```

## Rules

- Queue execution depends on external Redis and RQ worker processes.
- API embedded stale-job reaper is disabled by default; production scheduler/reaper work should run outside API replicas.
- `scripts/start-dev.ps1` starts profile/auth workers, not warmup workers.
- Warmup workers are started manually only when testing the warmup module.
- Worker diagnostics must report the production queue taxonomy.
- Runtime role metadata lives in `backend/app/runtime/roles.py`; optional
  `run_worker --role ...` validation enforces role-to-queue allowlists while
  preserving raw `--queues` compatibility.
- Reserved `media_jobs`, `story_jobs`, and `account_lifecycle_jobs` belong to
  `maintenance_worker` until dedicated roles exist.
- Feature-specific enqueue ownership lives in module enqueue helpers such as
  `app.modules.account_editing.enqueue` and `app.modules.warmup.enqueue`;
  `app.job_queue.rq` keeps compatibility wrapper imports.

## References

- `backend/app/services/worker_plane.py`
- `backend/app/job_queue/rq.py`
- `docs/runbooks/workers-production-plane.md`
- `docs/runtime/runtime-boundaries.md`
