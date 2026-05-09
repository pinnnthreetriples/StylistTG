# Staging Backend Worker Deploy

## Goal

Deploy the staging FastAPI backend and RQ worker against the dev/staging cloud contour: Neon Postgres, Supabase Auth, Upstash Redis, and Backblaze B2/S3 asset storage.

No live Telegram/TDLib writes are part of this stage.

## Services

1. Web service: FastAPI API process.
2. Worker service: RQ worker subscribed to `profile_jobs` and `auth_jobs`.
3. One-off migration job: Alembic upgrade against Neon direct connection.

## Deployment Target

The repo includes `backend/Dockerfile` and `render.yaml` as the primary Render-ready path. The commands are deployment-neutral and also map directly to Railway or Fly services.

Do not put secrets in `render.yaml`, Railway config, Fly config, Dockerfile, or committed env files.

## Order

1. Set env secrets in the hosting provider.
2. Run the migration job with `DATABASE_DIRECT_URL`.
3. Start the backend web service.
4. Start the worker service.
5. Run `staging_smoke`.
6. Keep `PROFILE_EXECUTION_ADAPTER=mock`.
7. Do not enable TDLib live until a separate TDLib runtime PR covers persistent volumes, libtdjson packaging, and session isolation.

## Commands

Web:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Worker:

```bash
python -m app.workers.run_worker --queues profile_jobs,auth_jobs
```

Queue-specific worker launcher is available for the production execution-plane foundation:

```bash
python -m app.workers.run_worker --queues auth_jobs
python -m app.workers.run_worker --queues profile_jobs
python -m app.workers.run_worker --queues account_lifecycle_jobs,maintenance_jobs
```

Keep the compatibility worker command unless the hosting provider is explicitly split into queue-specific worker services.

Migration:

```bash
python -m alembic upgrade head
```

Smoke:

```bash
python -m app.scripts.staging_smoke --base-url https://<staging-backend> --include-storage --env-file .env.cloud.local
```

Use `--allow-write-cloud` only when an object write/read/delete smoke is intended.

## Environment Variables

Required web and worker runtime:

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
STORAGE_S3_ENDPOINT_URL=https://s3.eu-central-003.backblazeb2.com
STORAGE_S3_BUCKET=stylisttg-dev-assets-pnn2026
STORAGE_S3_REGION=eu-central-003
STORAGE_S3_FORCE_PATH_STYLE=true
STORAGE_S3_ACCESS_KEY_ID=<secret>
STORAGE_S3_SECRET_ACCESS_KEY=<secret>
STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS=300
PROFILE_EXECUTION_ADAPTER=mock
STALE_JOB_REAPER_ENABLED=false
ENFORCE_LOCALHOST_ONLY=false
CORS_ORIGINS=https://<dashboard-domain>
LOG_TO_FILE=false
TDLIB_SHARED_LIBRARY_PATH=
TDLIB_DATABASE_ROOT=/var/lib/stylisttg/tdlib/database
TDLIB_FILES_ROOT=/var/lib/stylisttg/tdlib/files
TDLIB_STORAGE_BACKEND=local
TDLIB_LIVE_ENABLED=false
ACCOUNT_EXPORT_TTL_DAYS=7
ACCOUNT_DELETION_LOG_RETENTION_DAYS=90
ACCOUNT_DELETION_ALLOW_HARD_DELETE=false
ACCOUNT_DELETION_DRY_RUN_DEFAULT=true
SCHEDULER_ENABLED=false
REAPER_ENABLED=false
REAPER_MODE=dry_run
RATE_LIMIT_AUTH_JOBS_PER_TENANT_PER_HOUR=20
RATE_LIMIT_PROFILE_JOBS_PER_TENANT_PER_HOUR=100
RATE_LIMIT_MEDIA_JOBS_PER_TENANT_PER_HOUR=50
RATE_LIMIT_STORY_JOBS_PER_TENANT_PER_HOUR=20
RATE_LIMIT_ACCOUNT_JOBS_PER_HOUR=10
```

Migration-only:

```text
DATABASE_DIRECT_URL=<Neon direct URL>
DATABASE_URL=<Neon direct URL>
```

Web runtime should not require `DATABASE_DIRECT_URL` if migrations run as a separate job. Do not run Alembic through the pooled Neon URL.

## Health And Readiness

- `/health` returns `200` with process liveness only.
- `/ready` checks DB and Redis.
- `/ready` returns `503` if DB or Redis is down.
- TDLib `not_configured` does not fail readiness while `PROFILE_EXECUTION_ADAPTER=mock`.
- Storage belongs in diagnostics/smoke. It is not a hard readiness dependency unless a later deployment policy explicitly makes it one.
- Responses must not include secrets or full connection strings.

## Staging Smoke Checklist

1. `python -m app.scripts.staging_smoke --base-url https://<staging-backend> --include-storage --env-file .env.cloud.local`
2. Confirm `/health`, `/ready`, and `/diagnostics/runtime` pass.
3. Confirm `cloud_config_check` passes or only reports understood warnings.
4. Confirm Neon runtime and Alembic current checks pass.
5. Confirm Supabase JWKS fetch passes.
6. Confirm Upstash Redis ping/temp-key roundtrip passes.
7. Confirm object storage is dry-run unless `--allow-write-cloud` is explicitly supplied.
8. Confirm no live TDLib, live profile, story, music, cleanup, or reaper action was run.

## Backblaze B2

- Endpoint format: `https://s3.<region>.backblazeb2.com`.
- Region comes from the endpoint, for example `eu-central-003`.
- `keyID` is `STORAGE_S3_ACCESS_KEY_ID`.
- `applicationKey` is `STORAGE_S3_SECRET_ACCESS_KEY`.
- Keep the bucket private.
- Signed URLs are only for application asset keys, never TDLib sessions.

## Upstash Redis

- Use the `rediss://` TCP URL.
- Do not use the Upstash REST URL for RQ.
- Do not run `FLUSHDB` or `KEYS`.
- Smoke uses only `ping`, temporary `set/get/delete`, and a `smoke:stylisttg` key prefix.

## TDLib

- Staging backend/worker deploy uses `PROFILE_EXECUTION_ADAPTER=mock`.
- TDLib live runtime requires a separate PR for persistent volume layout, `libtdjson` image packaging, and session isolation.
- Do not mount real sessions until reviewed.
- Do not run live profile, story, music, or auth write jobs as part of this staging deploy readiness PR.
- Scheduler/reaper remain disabled and dry-run/report-only by default.
- Account deletion/export requests are auditable foundations; hard delete remains disabled unless a future reviewed operational workflow enables it.

## Rollback

1. Stop the worker first.
2. Roll back the web image/service.
3. Do not downgrade the database automatically.
4. Preserve storage objects.
5. Do not delete Redis keys manually except keys under the smoke prefix.

## Render Notes

- `render.yaml` defines a Docker web service and Docker worker service.
- Provider secrets remain `sync: false`.
- Run migration as a one-off command with `DATABASE_DIRECT_URL` set for that job.

## Railway Notes

- Create two services from the same Dockerfile.
- Set the web start command to the web command above.
- Set the worker start command to the RQ worker command above.
- Run migration as a one-off Railway command with the direct Neon URL.

## Fly Notes

- Use the same Dockerfile.
- Define separate process groups for web and worker.
- Attach a persistent volume only in the later TDLib runtime PR, not in this staging mock deploy.

## Northflank Notes

Use `docs/runbooks/northflank-staging-readiness.md` as the provider-specific
readiness checklist. It keeps Northflank config changes separate from code
changes and treats this stage as mock-safe SaaS staging validation.
