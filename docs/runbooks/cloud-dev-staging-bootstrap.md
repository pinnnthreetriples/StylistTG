# Cloud Dev/Staging Bootstrap

## Goal

Create a controlled dev/staging cloud contour for StylistTG SaaS without
touching live Telegram accounts or production data.

## Required Services

- Neon Postgres for primary PostgreSQL.
- Supabase Auth as the identity provider only.
- Cloudflare R2 or another S3-compatible object store for application assets.
- Managed Redis-compatible service for queues/cache.

FastAPI remains the only application data access layer. The frontend must not
access the database directly, and Supabase RLS is not the primary tenant
boundary.

## Resource Naming

Use explicit dev/staging names only:

- `stylisttg-dev`
- `stylisttg-staging`
- `stylisttg-dev-assets`
- `stylisttg-staging-assets`

Do not create production resources from this bootstrap flow.

## Neon Setup

1. Create a Neon dev/staging project or branch.
2. Copy the pooled runtime connection URL to `DATABASE_RUNTIME_URL`.
3. Copy the direct connection URL to `DATABASE_DIRECT_URL`.
4. Set `DATABASE_URL=${DATABASE_RUNTIME_URL}` for runtime compatibility.
5. Run migrations only through the direct URL:

   ```powershell
   cd backend
   python -m alembic upgrade head
   ```

Use the smoke command before migrations:

```powershell
cd backend
python -m app.scripts.cloud_config_check
python -m app.scripts.neon_smoke --readonly
python -m app.scripts.neon_smoke --check-migrations
```

Add `--upgrade-head` only when you intentionally want to migrate dev/staging.

## Supabase Auth Setup

1. Create a Supabase dev/staging project.
2. Configure Auth.
3. Set:
   - `SUPABASE_AUTH_JWKS_URL=https://<project>.supabase.co/auth/v1/.well-known/jwks.json`
   - `SUPABASE_AUTH_ISSUER=https://<project>.supabase.co/auth/v1`
   - `SUPABASE_AUTH_AUDIENCE=authenticated`
4. Do not put Supabase service-role keys in frontend env.
5. Backend verifies JWTs through JWKS and then enforces workspace/roles.

Smoke:

```powershell
cd backend
python -m app.scripts.supabase_auth_smoke
```

If `TEST_SUPABASE_JWT` is provided, the script verifies it without printing the
token.

## R2/S3 Setup

For Cloudflare R2:

1. Create a dev/staging bucket, for example `stylisttg-dev-assets`.
2. Create a limited token scoped to that bucket with Object Read & Write.
3. Set:
   - `STORAGE_BACKEND=s3`
   - `STORAGE_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com`
   - `STORAGE_S3_REGION=auto`
   - `STORAGE_S3_FORCE_PATH_STYLE=true`
4. Do not make the bucket public by default.

Smoke:

```powershell
cd backend
python -m app.scripts.object_storage_smoke
python -m app.scripts.object_storage_smoke --allow-write-cloud
```

Default mode is dry-run. Write mode creates, reads, signs, and deletes only a
single object under `smoke/stylisttg/<uuid>/`.

## Redis Setup

Use a managed Redis-compatible endpoint. Prefer TLS:

```text
REDIS_URL=rediss://...
```

Smoke:

```powershell
cd backend
python -m app.scripts.redis_smoke
```

The Redis smoke uses one temporary key with prefix `smoke:stylisttg:`. It never
runs `FLUSHDB`, `KEYS *`, or full scans.

## Smoke Order

1. `python -m app.scripts.cloud_config_check`
2. `python -m app.scripts.neon_smoke --readonly`
3. `python -m app.scripts.supabase_auth_smoke`
4. `python -m app.scripts.redis_smoke`
5. `python -m app.scripts.object_storage_smoke`
6. `python -m app.scripts.object_storage_smoke --allow-write-cloud`
7. `python -m app.scripts.neon_smoke --check-migrations --upgrade-head`

The combined orchestrator runs the safe default set:

```powershell
cd backend
python -m app.scripts.cloud_smoke --safe-default --include-redis --include-storage
```

Object storage writes require `--allow-write-cloud`. Migrations require
`--allow-migrations`.

## Safety Rules

- No live Telegram/TDLib write smoke.
- No profile/story/music jobs.
- No cleanup/reaper.
- No TDLib session migration.
- No production resources.
- No committed secrets.
- No direct frontend DB access.
- No Supabase service-role key in frontend.

## Troubleshooting

- Pooled/direct URL mix-up: runtime host should usually contain `-pooler`, direct
  migration host should not.
- Missing JWKS keys: check Supabase Auth asymmetric signing/JWKS availability.
- R2 endpoint mismatch: use `https://<account_id>.r2.cloudflarestorage.com` and
  region `auto`.
- Redis TLS issues: prefer `rediss://`; validate provider CA/TLS settings.
- Bucket permission denied: confirm token is scoped to the dev/staging bucket.
- Migration through pooler: use `DATABASE_DIRECT_URL`, not the pooled runtime URL.

