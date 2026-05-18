# Northflank Staging Readiness

This runbook verifies the current StylistTG staging contour on Northflank without
changing cloud resources or enabling live TDLib mutations.

## Scope

Northflank runs two services from the same repository image:

- API service: FastAPI web process.
- Worker service: RQ worker process.

Northflank is the runtime only. Business data and dependencies live in Neon,
Upstash Redis, Backblaze B2/S3-compatible storage, and Supabase Auth.

Do not use this checklist to enable live profile, story, music, bulk import,
cleanup, or destructive reaper behavior.

## Expected Northflank Services

API service command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Worker service command:

```bash
python -m app.workers.run_worker --queues profile_jobs,auth_jobs
```

Northflank staging may keep one worker service and group reserved queues with
raw `--queues` mode when resource limits do not allow separate services:

```bash
python -m app.workers.run_worker --queues maintenance_jobs,media_jobs,story_jobs,account_lifecycle_jobs
```

Queue-specific role commands are available for later service splits:

```bash
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues maintenance_jobs --role maintenance_worker
python -m app.workers.run_worker --queues media_jobs --role media_worker
python -m app.workers.run_worker --queues story_jobs --role story_worker
python -m app.workers.run_worker --queues account_lifecycle_jobs --role account_lifecycle_worker
```

Keep compatibility worker commands until the Northflank deployment is explicitly
split into queue-specific workers.

## Required Runtime Env

Set these on both API and worker unless noted otherwise:

```text
APP_ENV=staging
AUTH_MODE=supabase_jwt
DB_CONNECTION_MODE=neon
DATABASE_URL=<Neon pooled runtime URL>
DATABASE_RUNTIME_URL=<Neon pooled runtime URL>
SUPABASE_AUTH_JWKS_URL=<Supabase JWKS URL>
SUPABASE_AUTH_ISSUER=<Supabase auth issuer>
SUPABASE_AUTH_AUDIENCE=authenticated
REDIS_URL=rediss://<Upstash TCP Redis URL>
STORAGE_BACKEND=s3
STORAGE_S3_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
STORAGE_S3_BUCKET=<private staging bucket>
STORAGE_S3_REGION=<b2 region>
STORAGE_S3_ACCESS_KEY_ID=<secret>
STORAGE_S3_SECRET_ACCESS_KEY=<secret>
STORAGE_S3_FORCE_PATH_STYLE=true
STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS=300
PROFILE_EXECUTION_ADAPTER=mock
TDLIB_LIVE_ENABLED=false
TDLIB_RUNTIME_MODE=mock
TDLIB_READONLY_SMOKE_ENABLED=false
TDLIB_DATABASE_ROOT=/var/lib/stylisttg/tdlib/database
TDLIB_FILES_ROOT=/var/lib/stylisttg/tdlib/files
ACCOUNT_DELETION_ALLOW_HARD_DELETE=false
SCHEDULER_ENABLED=false
REAPER_ENABLED=false
REAPER_MODE=dry_run
```

API service observability env:

```text
BETTER_STACK_API_DSN=<Better Stack Errors API DSN>
SENTRY_ENVIRONMENT=staging
SENTRY_RELEASE=<release identifier>
```

Worker service observability env:

```text
BETTER_STACK_WORKER_DSN=<Better Stack Errors worker DSN>
SENTRY_ENVIRONMENT=staging
SENTRY_RELEASE=<release identifier>
```

Migration-only env:

```text
DATABASE_DIRECT_URL=<Neon direct URL>
DATABASE_URL=<Neon direct URL>
```

Do not run Alembic through the Neon pooled runtime URL.

Frontend build/runtime env:

```text
VITE_API_BASE_URL=<Northflank API URL>
VITE_SUPABASE_URL=<Supabase project URL>
VITE_SUPABASE_PUBLISHABLE_KEY=<Supabase publishable key>
VITE_APP_ENV=staging
VITE_BETTER_STACK_DASHBOARD_DSN=<Better Stack Errors dashboard DSN>
VITE_SENTRY_RELEASE=<release identifier>
```

Never expose Supabase service-role keys, DB URLs, Redis URLs, B2 credentials,
Telegram API hash, proxy passwords, JWTs, or TDLib session paths to frontend env.

## Readiness Checks

From the backend directory with a filled ignored `.env.cloud.local`:

```powershell
python -m app.scripts.cloud_config_check --json
python -m app.scripts.staging_smoke --base-url https://<northflank-api-host> --include-storage --allow-write-cloud --env-file ../.env.cloud.local
```

The staging smoke checks:

- `/health`;
- `/ready`;
- `/diagnostics/runtime`;
- cloud env contract;
- Neon runtime connection and migration state;
- Supabase JWKS;
- Upstash Redis ping/temp-key roundtrip;
- optional Backblaze B2 object storage write/read/delete under `smoke/stylisttg/...`.

Expected endpoint behavior:

- `/health` returns `200` when the API process is alive.
- `/ready` returns `200` only when DB and Redis are reachable.
- `/ready` returns `503` when DB or Redis is down.
- `/diagnostics/runtime` returns structured status without secrets.
- `/diagnostics/frontend-summary` returns dashboard-safe metadata only.

## Provider Checks

Neon:

- API and worker use the pooled runtime URL.
- Migration job uses the direct URL.
- Alembic command: `python -m alembic upgrade head`.

Supabase:

- Backend verifies JWTs through JWKS.
- Frontend uses only publishable/public config.
- Service-role keys never appear in frontend env, diagnostics, OpenAPI output, or browser artifacts.

Backblaze B2/S3:

- Bucket remains private.
- Signed URLs are only for non-sensitive application assets.
- TDLib database/files/session data never use object storage or public URLs.
- Smoke writes only under `smoke/stylisttg/...`.

Upstash Redis:

- Use TCP `rediss://`, not REST URL, for RQ.
- Redis backs queues, locks, rate limits, cooldowns, and readiness.
- Do not run `FLUSHDB`, `KEYS`, or manual key deletion outside smoke keys.

## Deploy Checklist

1. Confirm PR is merged into `main`.
2. Confirm GitHub Backend, Frontend, and Browser QA checks pass.
3. Run migration as a one-off job with the direct Neon URL.
4. Deploy/restart the API service.
5. Deploy/restart the worker service.
6. Run staging smoke with storage enabled.
7. Confirm Northflank API and worker are both running.
8. Confirm `PROFILE_EXECUTION_ADAPTER=mock` and `TDLIB_LIVE_ENABLED=false`.
9. Confirm Health Center shows API, DB, Redis, storage, worker, and TDLib posture.

## Rollback Checklist

1. Stop or pause the worker first.
2. Roll back the API image/service to the previous known-good commit.
3. Do not downgrade Neon automatically.
4. Preserve B2 objects and audit rows.
5. Do not delete Redis keys except smoke keys created by this run.
6. Re-run `/health`, `/ready`, and staging smoke after rollback.

## Hard Stops

Stop and investigate if any of these occur:

- `cloud_config_check` reports `FAIL`.
- `/ready` fails after API restart.
- Redis smoke cannot roundtrip a temp key.
- Supabase JWKS fetch fails.
- Object storage smoke writes outside `smoke/stylisttg/...`.
- Diagnostics contain secret-like values or raw URLs.
- `TDLIB_LIVE_ENABLED=true` without explicit reviewed live validation.
- `PROFILE_EXECUTION_ADAPTER=tdlib` in normal staging.
- Scheduler/reaper destructive mode is enabled.
