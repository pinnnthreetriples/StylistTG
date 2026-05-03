# Controlled Live Auth Validation

## Purpose

Validate one explicit Telegram authorization flow in an isolated dev/staging
environment. This runbook is not a production launch and must not enable live
profile, story, music, bulk import, cleanup, or reaper execution.

## Preconditions

- A dedicated test Telegram account is available.
- The operator has explicit approval to run a live auth test.
- `libtdjson` is installed or mounted at `TDLIB_SHARED_LIBRARY_PATH`.
- TDLib database/files roots point to an isolated private volume.
- Redis, database, and API are reachable from the auth worker.
- No real credentials are written into docs, Git history, logs, screenshots, or
  Playwright artifacts.

## Required Environment

```text
TDLIB_LIVE_ENABLED=true
TDLIB_READONLY_SMOKE_ENABLED=true
PROFILE_EXECUTION_ADAPTER=mock
TDLIB_RUNTIME_MODE=live
TDLIB_SHARED_LIBRARY_PATH=/usr/local/lib/libtdjson.so
TDLIB_DATABASE_ROOT=/var/lib/stylisttg/tdlib/database
TDLIB_FILES_ROOT=/var/lib/stylisttg/tdlib/files
TELEGRAM_API_ID=<operator-provided>
TELEGRAM_API_HASH=<operator-provided>
```

Diagnostics may show only configured booleans. They must never show the API hash
or raw TDLib paths.

## Forbidden Actions

- Do not run profile/story/music jobs.
- Do not enable bulk login or mass import.
- Do not run cleanup/reaper in destructive mode.
- Do not delete TDLib session directories.
- Do not store or log Telegram auth codes or 2FA passwords.
- Do not reuse one TDLib database/files directory across accounts.

## Validation Steps

1. Confirm current app safety posture:

   ```powershell
   cd backend
   python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check --json
   ```

2. Start only the auth worker:

   ```powershell
   python -m app.workers.run_worker --queues auth_jobs
   ```

3. Start one auth session from the dashboard or API for the dedicated test
   account.

4. Submit the Telegram code manually. If 2FA is enabled, submit the password
   manually. Codes and passwords must not be persisted or queued.

5. Poll auth session status until it reaches `ready` or a safe error state.

6. Verify the only Telegram read performed after authorization is the safe
   identity/readiness check required to link the account.

7. Verify audit events exist for start, code/password submission, completion, or
   failure. Audit metadata must not contain the code, password, API hash, TDLib
   paths, or session data.

8. Verify Health Center and worker diagnostics:

   - TDLib live enabled only in this isolated environment;
   - library loadable;
   - readonly smoke available;
   - execution plane ready only for auth/readiness.

## Abort Criteria

Abort immediately if:

- diagnostics expose raw paths or secrets;
- auth code/password appears in logs, queue metadata, API responses, or frontend
  state after submit;
- the worker attempts profile/story/music execution;
- the account shares TDLib storage with another account/session;
- Redis locks/rate limits/cooldowns do not behave as expected.

## Rollback

1. Stop the auth worker.
2. Set `TDLIB_LIVE_ENABLED=false`.
3. Set `TDLIB_READONLY_SMOKE_ENABLED=false`.
4. Keep `PROFILE_EXECUTION_ADAPTER=mock`.
5. Preserve audit records.
6. Do not delete session directories unless a reviewed account deletion workflow
   explicitly approves it.

## Evidence Checklist

- Runtime smoke JSON result.
- Sanitized Health Center screenshot.
- Auth session status transition summary.
- Audit event IDs and action names.
- Confirmation that no profile/story/music jobs ran.
- Confirmation that no secrets or raw TDLib paths appeared in logs/API/UI.

## Readiness Criteria

The environment is ready for the next review only when one test account completes
auth or reaches a known safe error state, all evidence is collected, staging smoke
still passes, and live profile/story/music execution remains disabled.
