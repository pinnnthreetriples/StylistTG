# TDLib Runtime Runbook

## Safe Checks

Runtime/library checks do not perform Telegram network actions:

```powershell
cd backend
python scripts/verify_tdlib_runtime.py
python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check
```

Expected staging/default posture:

```text
TDLIB_LIVE_ENABLED=false
TDLIB_RUNTIME_MODE=mock
PROFILE_EXECUTION_ADAPTER=mock
```

Missing `libtdjson` is not a deployment blocker for mock staging.

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
