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

## TDLib Worker Image

The current `backend/Dockerfile` remains the API and standard worker image. The
`backend/Dockerfile.tdlib` builds a worker image with `libtdjson` baked into:

```text
/usr/local/lib/libtdjson.so
```

Use this Dockerfile for the Northflank worker service when cloud TDLib live
execution is being validated. Do not switch the API service to this image.

To keep Northflank builds short, this Dockerfile does not compile TDLib from
source. It copies `libtdjson.so` from the prebuilt GHCR image:

```text
ghcr.io/pinnnthreetriples/stylisttg-tdlib-worker:main
```

Manual build, when Docker is available:

```powershell
docker build -f backend/Dockerfile.tdlib -t stylisttg-backend-tdlib:test .
```

The prebuilt base image is published by GitHub Actions:

```text
ghcr.io/pinnnthreetriples/stylisttg-tdlib-worker:main
ghcr.io/pinnnthreetriples/stylisttg-tdlib-worker:sha-<commit>
```

The workflow lives at:

```text
.github/workflows/tdlib-worker-image.yml
```

It runs on `main` when the TDLib worker image inputs change, and can also be
started manually from GitHub Actions. Northflank should then pull the ready
`libtdjson.so` layer from GHCR instead of compiling TDLib itself.

Before running it as a live worker, provide `TDLIB_SHARED_LIBRARY_PATH` and
private TDLib roots:

```text
TDLIB_SHARED_LIBRARY_PATH=/usr/local/lib/libtdjson.so
TDLIB_DATABASE_ROOT=/var/lib/stylisttg/tdlib/database
TDLIB_FILES_ROOT=/var/lib/stylisttg/tdlib/files
```

For a two-service Northflank staging contour, keep the API service on the normal
image and switch only `stylisttg-staging-worker` to `backend/Dockerfile.tdlib`.
The worker command can listen to all live-capable queues:

```bash
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json && python -m app.workers.run_worker --queues auth_jobs,profile_jobs,media_jobs,story_jobs
```

Do not set `TDLIB_LIVE_ENABLED=true` until the controlled live auth validation
runbook has been followed in an isolated staging/dev environment.

For persistent Telegram sessions, mount a private worker volume for
`TDLIB_DATABASE_ROOT` and `TDLIB_FILES_ROOT`. Temporary paths such as `/tmp`
are acceptable only for disposable smoke validation because they are lost on
redeploy.

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
