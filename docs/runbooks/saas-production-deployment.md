# SaaS Production Deployment Runbook

This runbook is for the FastAPI backend. The frontend must not connect to the database directly.

## Required Environment

Database:

```powershell
APP_ENV=production
DB_CONNECTION_MODE=neon
DATABASE_RUNTIME_URL=<neon pooled runtime connection string>
DATABASE_DIRECT_URL=<neon direct/admin migration connection string>
DB_POOL_PRE_PING=true
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

`DATABASE_URL` can be used as a fallback, but production should keep runtime and migration URLs separate.
Run migrations with the direct URL. Run the API and workers with the pooled runtime URL.

Auth:

```powershell
AUTH_MODE=supabase_jwt
ALLOW_LOCAL_AUTH_IN_PROD=false
SUPABASE_AUTH_JWKS_URL=<supabase JWKS URL>
SUPABASE_AUTH_ISSUER=<supabase issuer>
SUPABASE_AUTH_AUDIENCE=<supabase audience if configured>
SUPABASE_AUTH_JWKS_CACHE_TTL_SECONDS=600
SUPABASE_AUTH_JWKS_REFRESH_ON_KID_MISS=true
SUPABASE_AUTH_JWKS_REQUEST_TIMEOUT_SECONDS=5
SUPABASE_AUTH_JWKS_MAX_RETRIES=1
```

`AUTH_MODE=local` is blocked in production/cloud mode unless `ALLOW_LOCAL_AUTH_IN_PROD=true` is explicitly set.
Use that override only for controlled non-production testing.

Redis:

```powershell
REDIS_URL=<redis URL>
```

Secrets and runtime:

```powershell
PROXY_CREDENTIALS_ENCRYPTION_KEY=<fernet key>
TDLIB_API_ID=<telegram api id>
TDLIB_API_HASH=<telegram api hash>
TDLIB_DATABASE_ROOT=<private TDLib database path>
TDLIB_FILES_ROOT=<private TDLib files path>
TDLIB_SHARED_LIBRARY_PATH=<tdjson library path>
PROFILE_EXECUTION_ADAPTER=tdlib
```

Do not expose Supabase service-role keys, proxy passwords, JWTs, TDLib sessions, or TDLib storage paths to the browser.

## Deployment Order

1. Set environment variables.
2. Validate that `APP_ENV=production`, `AUTH_MODE=supabase_jwt`, and `DB_CONNECTION_MODE=neon`.
3. Run migrations with the direct DB URL:

   ```powershell
   cd backend
   python -m alembic upgrade head
   ```

4. Start the FastAPI backend with the pooled runtime DB URL.
5. Start separate RQ workers:

   ```powershell
   cd backend
   python -m rq.cli worker profile_jobs --url <redis URL> --worker-class rq.SimpleWorker
   python -m rq.cli worker auth_jobs --url <redis URL> --worker-class rq.SimpleWorker
   ```

6. Check:

   ```text
   /health
   /ready
   /diagnostics/runtime
   ```

7. Run non-live smoke only:

   - database is reachable;
   - Redis is reachable;
   - workers are visible;
   - auth mode is not local;
   - Alembic head is current.

## Safety Rules

- Do not run live Telegram write smoke automatically on production accounts.
- Do not expose the backend without HTTPS or a trusted reverse proxy.
- Do not use `AUTH_MODE=local` in production.
- Do not give frontend direct database access.
- Do not expose Supabase service-role keys.
- Do not expose TDLib session folders through public storage.

## Rollback Notes

- Take a database backup before production migrations.
- Stop workers before risky migrations so no queued job mutates state during schema changes.
- If migration rollback is required, validate the downgrade path on a staging copy first.
- Re-enable workers only after `/ready` and migration status are healthy.
