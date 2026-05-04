# TDLib Runtime Runbook

## Safe Checks

Runtime/library checks do not perform Telegram network actions:

```powershell
cd backend
python scripts/verify_tdlib_runtime.py
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json
```

Expected staging/default posture:

```text
TDLIB_LIVE_ENABLED=false
TDLIB_RUNTIME_MODE=mock
PROFILE_EXECUTION_ADAPTER=mock
```

Missing `libtdjson` is not a deployment blocker for mock staging.

The smoke command returns `PASS` in mock/staging mode when the library is not
configured. If `TDLIB_SHARED_LIBRARY_PATH` is configured, `--library-check`
requires the library to load and expose the expected TDLib JSON symbols.

## Optional TDLib Worker Image

The current `backend/Dockerfile` remains the API and standard worker image. The
optional `backend/Dockerfile.tdlib` is reserved for future auth workers that need
`libtdjson` and isolated TDLib volume mounts.

Manual build, when Docker is available:

```powershell
docker build -f backend/Dockerfile.tdlib -t stylisttg-backend-tdlib:test .
```

Before running it as a live auth worker, provide `TDLIB_SHARED_LIBRARY_PATH` and
mount or bake the library at that location:

```text
TDLIB_SHARED_LIBRARY_PATH=/usr/local/lib/libtdjson.so
TDLIB_DATABASE_ROOT=/var/lib/stylisttg/tdlib/database
TDLIB_FILES_ROOT=/var/lib/stylisttg/tdlib/files
```

Do not set `TDLIB_LIVE_ENABLED=true` until the controlled live auth validation
runbook has been followed in an isolated staging/dev environment.

## Optional Read-Only Smoke

Read-only auth smoke is disabled unless explicitly enabled:

```powershell
$env:TDLIB_LIVE_ENABLED="true"
$env:TDLIB_READONLY_SMOKE_ENABLED="true"
python -m app.scripts.tdlib_runtime_smoke --readonly-auth-check --auth-session-id <id>
```

This mode must use an existing auth session and must not mutate profile, stories, media, or account lifecycle state.

## Secrets

Never print or commit:

- `TELEGRAM_API_HASH`;
- auth code or 2FA password;
- TDLib database/files paths;
- session/auth keys.
