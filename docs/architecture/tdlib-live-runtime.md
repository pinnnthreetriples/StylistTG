# TDLib Live Runtime Foundation

Live TDLib remains disabled by default. This foundation adds runtime detection, isolated storage paths, auth-only client lifecycle primitives, and diagnostics without enabling profile/story/music execution.

## Runtime Packaging

The existing API image remains compatible and remains the default deployment path. Live workers may either mount/provide `libtdjson` through `TDLIB_SHARED_LIBRARY_PATH` or use the optional TDLib worker image scaffold in `backend/Dockerfile.tdlib`. That image does not change the current API/worker deployment and still defaults to mock mode.

The verification helper checks loadability without starting Telegram network actions:

```powershell
cd backend
python scripts/verify_tdlib_runtime.py
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json
```

If the library is absent, diagnostics report `not_configured` and mock mode continues to work.

## Configuration

Safe defaults:

```text
TDLIB_LIVE_ENABLED=false
TDLIB_RUNTIME_MODE=mock
PROFILE_EXECUTION_ADAPTER=mock
TDLIB_READONLY_SMOKE_ENABLED=false
```

Live auth additionally requires operator-provided `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. Diagnostics expose only configured booleans, never the API hash or raw TDLib paths.

## Storage Isolation

`backend/app/services/tdlib_paths.py` builds internal-only TDLib database/files paths by workspace and account or auth-session ID:

```text
<TDLIB_DATABASE_ROOT>/<workspace_id>/<account_id>/
<TDLIB_DATABASE_ROOT>/<workspace_id>/auth-sessions/<auth_session_id>/
```

Path segments are sanitized and traversal is rejected. Public diagnostics must not return absolute paths.

## Live Gates

Any future live operation must pass:

- explicit live config;
- TDLib library and Telegram API credentials configured;
- workspace/account or auth-session lock;
- tenant/account rate limit;
- cooldown check;
- risk gate and audited override where required;
- allowlisted job type;
- audit event and idempotency protection.

This PR only adds auth/readiness foundations. It does not add live profile/story/music mutations.
