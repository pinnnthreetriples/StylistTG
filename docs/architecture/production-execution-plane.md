# Production Execution Plane

The production execution plane is a safety foundation for future live Telegram work. Live TDLib execution remains disabled by default.

## Queue Taxonomy

- `auth_jobs`: Telegram auth/login/reauth jobs.
- `profile_jobs`: profile/account-update jobs.
- `media_jobs`: media upload/normalization jobs.
- `story_jobs`: story jobs.
- `account_lifecycle_jobs`: deletion/export/lifecycle jobs.
- `maintenance_jobs`: safe maintenance/reaper reports.
- `scheduler_jobs`: future scheduled enqueue/report jobs.

Current staging worker commands remain compatible. New dedicated worker launchers can use:

```powershell
cd backend
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
```

The launcher rejects unknown queue names.

## Locks

`backend/app/services/locks.py` now includes Redis owner-token locks:

- `locks:account:<workspace_id>:<account_id>:execution`
- `locks:account:<workspace_id>:<account_id>:lifecycle`

Locks have TTLs, release only by matching owner token, and never rely on infinite leases.

## Rate Limits

`backend/app/services/rate_limits.py` uses Redis counters with TTLs for tenant/account/job dimensions. Defaults:

```text
RATE_LIMIT_AUTH_JOBS_PER_TENANT_PER_HOUR=20
RATE_LIMIT_PROFILE_JOBS_PER_TENANT_PER_HOUR=100
RATE_LIMIT_MEDIA_JOBS_PER_TENANT_PER_HOUR=50
RATE_LIMIT_STORY_JOBS_PER_TENANT_PER_HOUR=20
RATE_LIMIT_ACCOUNT_JOBS_PER_HOUR=10
```

The decision shape includes `allowed`, reason, limit, remaining, and retry-after seconds.

## Cooldowns and Retry Policy

`backend/app/services/account_cooldowns.py` records account cooldowns from safe categorized errors such as `FLOOD_WAIT`.

`backend/app/services/retry_policy.py` categorizes failures:

- `flood_wait`: set cooldown, no immediate retry.
- `auth_required` and `validation_error`: no retry.
- `proxy_failed`, `tdlib_unavailable`, `unknown_transient`: bounded retry.
- `unknown_permanent`: no retry.

No policy allows infinite retry.

## Scheduler and Reaper

Scheduler and reaper are foundation-only:

```text
SCHEDULER_ENABLED=false
REAPER_ENABLED=false
REAPER_MODE=dry_run
```

`python -m app.scripts.run_scheduler` and `python -m app.scripts.run_reaper --mode dry_run` produce structured reports. They do not delete TDLib sessions, account assets, account rows, or audit logs.

## TDLib Live Safety

Live execution requires all gates:

- `TDLIB_LIVE_ENABLED=true`;
- `PROFILE_EXECUTION_ADAPTER=tdlib`;
- TDLib library and session roots configured;
- account lock acquired;
- tenant rate limit allows the action;
- risk gate passes or an allowed manual override is audited;
- job type is allowlisted;
- operation is audited and idempotency-protected.

Staging keeps:

```text
TDLIB_LIVE_ENABLED=false
PROFILE_EXECUTION_ADAPTER=mock
```

Diagnostics expose booleans such as `live_enabled`, `library_configured`, and `session_root_configured`, but never raw filesystem paths.
