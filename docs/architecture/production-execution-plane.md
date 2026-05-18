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
- `warmup_jobs`: dry-run account preparation jobs.
- `warmup_dispatch_jobs`: shadow/live warmup micro-session dispatch.

Current staging worker commands remain compatible. New dedicated worker launchers can use:

```powershell
cd backend
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues maintenance_jobs --role maintenance_worker
python -m app.workers.run_worker --queues media_jobs --role media_worker
python -m app.workers.run_worker --queues story_jobs --role story_worker
python -m app.workers.run_worker --queues account_lifecycle_jobs --role account_lifecycle_worker
python -m app.workers.run_worker --queues warmup_jobs
python -m app.workers.run_worker --queues warmup_dispatch_jobs
```

The launcher rejects unknown queue names. Optional runtime role validation is
documented in `docs/runtime/runtime-boundaries.md`; deployment process guidance
lives in `docs/runtime/deployment-processes.md`.
Raw `--queues` mode remains compatible for existing invocations; role-aware
startup validates that a worker role only consumes its owned queue.

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

Warmup has a separate enqueue ticker in the API lifespan. It is gated by `WARMUP_SCHEDULER_ENABLED`, `WARMUP_WORKERS_ENABLED`, and `WARMUP_HARD_DISABLE`. It only enqueues fixed-id RQ jobs; workers decide which sessions are due.

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

The auth/import foundation adds `telegram_auth_session`, `account_import_batch`, and `account_import_item` records plus auth/import API endpoints. These remain auth/readiness-only: they do not enqueue profile/story/music execution and they fail safely with `tdlib_live_disabled` when `TDLIB_LIVE_ENABLED=false`.

## Warmup Live Safety

Warmup dry-run sessions remain non-live and use `warmup_jobs`.

`warmup_dispatch_jobs` processes `shadow`, `passive`, `network`, and `advanced` execution modes. `shadow` is simulation-only. Live TDLib-backed warmup requires:

- `WARMUP_LIVE_ENABLED=true`;
- at least one live level enabled: `WARMUP_PASSIVE_ENABLED`, `WARMUP_NETWORK_ENABLED`, or `WARMUP_ADVANCED_ENABLED`;
- TDLib runtime configured and loadable;
- account isolation claim acquired for the warmup session;
- explicit operator approval before using real Telegram accounts.

Do not describe warmup as anti-ban, shadow-ban protection, behavior imitation, or a guarantee of Telegram account safety.
