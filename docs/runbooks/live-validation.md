# Live Validation Runbook

This runbook is for validating real TDLib behavior on an operator machine.

Live TDLib calls can affect a real Telegram account. Ask the user before running live operations.

## What This Validates

Current live path:

`auth -> refresh-runtime -> upload assets -> account-update preview -> account-update job -> RQ worker -> terminal job state`

The account update workflow can include:

- profile name/bio/username/photo;
- profile music upload/apply/remove;
- story image/video publishing;
- known active story deletion.

## Prerequisites

- Windows PowerShell.
- Python backend environment with dependencies.
- PostgreSQL reachable from backend.
- Redis-compatible server reachable at `redis://127.0.0.1:6379/0`.
- RQ worker process.
- `tdjson.dll`.
- `TDLIB_API_ID`.
- `TDLIB_API_HASH`.
- `PROXY_CREDENTIALS_ENCRYPTION_KEY` if testing proxy credentials with passwords.
- Optional `OPERATOR_API_TOKEN` if local mutating API calls should require `X-Operator-Token`.
- `ENFORCE_LOCALHOST_ONLY=true` is the safe default for the local operator API.
- One Telegram account that can receive OTP.
- Test media files only; avoid valuable/private media during validation.

Proxy notes:

- Proxy check is a technical connectivity check, not a Telegram profile operation.
- Proxy password storage uses Fernet encryption and requires `PROXY_CREDENTIALS_ENCRYPTION_KEY`.
- Do not print or commit `.env` / `backend/.env`; both may contain local proxy encryption keys.

Windows Redis preference:

- Use portable Memurai at `C:\Tools\Memurai` on this workstation.
- Do not use WSL Redis for this project; it has caused localhost/port instability.
- Docker Compose remains a portable option for PostgreSQL + Redis, but is not required here.

## Recommended Startup

From repo root:

```powershell
.\scripts\start-dev.ps1
```

This should start:

- Memurai Redis;
- backend API;
- RQ worker;
- Vite frontend.

If doing manual startup, use this order:

1. PostgreSQL
2. Redis/Memurai
3. backend API
4. RQ worker
5. frontend
6. live preflight
7. auth/runtime validation
8. account update validation

## Environment Variables

From `backend`:

```powershell
cd C:\Users\user\Documents\workspace-codex\StylistTG\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Set runtime configuration:

```powershell
$env:DATABASE_URL="postgresql+psycopg://stylisttg:stylisttg@localhost:5432/stylisttg"
$env:REDIS_URL="redis://127.0.0.1:6379/0"
$env:TDLIB_API_ID="<your api id>"
$env:TDLIB_API_HASH="<your api hash>"
$env:TDLIB_DATABASE_ROOT="C:\Users\user\Documents\workspace-codex\StylistTG\backend\tdlib\database"
$env:TDLIB_FILES_ROOT="C:\Users\user\Documents\workspace-codex\StylistTG\backend\tdlib\files"
$env:TDLIB_SHARED_LIBRARY_PATH="C:\path\to\tdjson.dll"
$env:PROFILE_EXECUTION_ADAPTER="tdlib"
```

Optional story live publishing:

```powershell
$env:STORIES_TDLIB_LIVE_ENABLED="true"
```

Do not enable story live publishing casually. Telegram story limits are real.

Apply migrations:

```powershell
python -m alembic upgrade head
```

## Start API Manually

From repo root:

```powershell
.\scripts\start_backend.ps1
```

Check the script output for the actual API port. Some local flows use `8002`; older examples may say `8000`.

## Start Worker Manually

In a second shell:

```powershell
.\scripts\start_worker.ps1
```

Worker must use the same Redis URL as API.

If jobs stay queued, verify:

- Redis is reachable;
- worker is running;
- worker listens to `profile_jobs` and `auth_jobs`;
- API and worker use the same `REDIS_URL`.

## Live Preflight

```powershell
.\scripts\live_preflight.ps1
```

Expected:

- `overall_status = ok`
- `tdjson_present = true`
- `tdlib_credentials_present = true`
- `postgres_reachable = true`
- `redis_reachable = true`
- `storage_writable = true`

If degraded, stop and fix the dependency first.

## Health and Readiness

Use the actual API port from startup output.

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/ready
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/diagnostics/runtime
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/diagnostics/live-preflight
```

Readiness contract:

- `/health` returns `200` if API process is alive.
- `/ready` returns `200` only when DB and Redis are OK.
- `/ready` returns `503` when DB or Redis is down.
- Diagnostics endpoints return structured payloads for troubleshooting.

## Auth Validation

Start OTP:

```powershell
.\scripts\live_auth_flow.ps1 -PhoneNumber "+15550102000"
```

After Telegram code arrives:

```powershell
.\scripts\live_auth_flow.ps1 -PhoneNumber "+15550102000" -AccountId "<account-id>" -Code "<otp-code>"
```

Expected after success:

- `authorized_ready` or `execution_usable`;
- `telegram_user_id` set;
- `authorized_last_confirmed_at` present.

If Telegram asks for 2FA, use the app UI or the auth password endpoint flow.

## Refresh Runtime

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/<account-id>/refresh-runtime
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/<account-id>/runtime-diagnostics
```

Expected:

- `account_state = execution_usable`
- `can_start_profile_job = true`
- `runtime_health = ready`

If not ready, do not start a live job.

## Account Update Validation

Preferred current workflow:

1. Upload needed assets:
   - `POST /api/assets/profile-photo`
   - `POST /api/assets/profile-audio`
   - `POST /api/assets/story-image`
   - `POST /api/assets/story-video`
2. Preview:
   - `POST /api/account-update/preview`
3. Create job:
   - `POST /api/account-update/jobs`
4. Poll:
   - `GET /api/accounts/jobs/latest`
   - `GET /api/jobs/{job_id}`
   - `GET /api/jobs/{job_id}/steps`

The old helper still validates the profile-photo path:

```powershell
.\scripts\live_profile_job.ps1 -AccountId "<account-id>" -PhotoPath "C:\path\to\profile.jpg" -Name "Alice" -Bio "Hello from StylistTG" -Username "alice_example" -WorkerLogPath "C:\path\to\worker.log"
```

For profile music and stories, prefer the UI or direct `/api/account-update/*` calls because the account-update workflow is the current expanded contract.

## Story Validation Notes

Before publishing stories:

- confirm `stories_enabled = true`;
- confirm `stories_tdlib_live_enabled = true` if using real TDLib story publish;
- check `GET /api/story-capabilities`;
- use disposable media;
- remember Telegram account limits.

Common real Telegram limit errors:

- `CAN_POST_STORY_ACTIVE_STORY_LIMIT_EXCEEDED`
- `CAN_POST_STORY_WEEKLY_LIMIT_EXCEEDED`

These are not necessarily app bugs.

## Profile Music Validation Notes

Supported intended execution formats:

- MP3
- M4A

Common errors:

- `PROFILE_AUDIO_UNSUPPORTED_FORMAT`
- `PROFILE_AUDIO_UPLOAD_NOT_COMPLETED`
- `PROFILE_AUDIO_FILE_ID_MISSING`
- `PROFILE_AUDIO_MESSAGE_SEND_FAILED`
- `PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT`
- `TDLIB_UNSUPPORTED_UPLOAD_FILE_METHOD`

If music upload/apply fails, inspect:

- uploaded asset metadata;
- `job-final.json`;
- `job-steps.json`;
- worker log;
- TDLib error payload in `result_payload_json`.

## Story Deletion Validation

Delete known active story:

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri http://127.0.0.1:8000/api/story-posts/<story-post-id> `
  -Headers @{ "X-Account-Id" = "<account-id>" }
```

Expected:

- HTTP `204`;
- dashboard refresh no longer shows the deleted story.

Possible errors:

- `STORY_POST_NOT_FOUND`
- `STORY_POST_CANNOT_DELETE`
- `STORY_DELETE_FAILED`

## Capture Artifacts

```powershell
.\scripts\capture_live_artifacts.ps1 -AccountId "<account-id>" -JobId "<job-id>" -WorkerLogPath "C:\path\to\worker.log"
```

Artifacts are written under:

- `artifacts/live-validation/<timestamp>-capture/`

Useful files:

- readiness JSON;
- diagnostics JSON;
- job final JSON;
- job steps JSON;
- worker log excerpt.

## Terminal State Interpretation

Good result:

- `completed`

Needs review but not always a full failure:

- `partially_completed`
- `manual_intervention_needed`

Failure:

- `failed`
- `canceled`

Common causes:

- `/ready = 503`: DB or Redis not ready.
- `overall_status = degraded`: fix live preflight dependency.
- `account_state = reauth_required`: restart auth flow.
- `account_state = runtime_broken`: inspect TDLib config/runtime directories.
- job stuck at `queued`: worker/Redis mismatch or worker stopped.
- username error: username may be occupied, invalid, purchasable, or ambiguous.
- story error: Telegram story limit or live story publishing disabled.
- music error: unsupported format or TDLib upload/file-id failure.

## Troubleshooting Notes

- If TDLib reaches `authorizationStateClosed`, do not reuse that client instance.
- If Redis is down, API may still answer `/health`, but `/ready` must be degraded.
- If PostgreSQL is down, `/ready` must be degraded.
- If jobs remain queued, verify worker process and Redis URL.
- If a Telegram operation fails, inspect the step result first; do not mask the error as success.
