# Live Validation Runbook

This runbook is for validating real TDLib behavior on an operator machine.

Live TDLib calls can affect a real account. Ask the operator before running live operations.

> Scope: Windows operator workstation profile. Replace `$RepoRoot`, `$ApiBaseUrl`, account IDs, phone numbers, media paths, and log paths with values from the current machine and startup output before copying commands.

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
- Separate worker processes for `profile_jobs` and `auth_jobs`; additional workers only for the module under validation.
- `tdjson.dll`.
- `TDLIB_API_ID`.
- `TDLIB_API_HASH`.
- `PROXY_CREDENTIALS_ENCRYPTION_KEY` if testing proxy credentials with passwords.
- Optional `OPERATOR_API_TOKEN` if local mutating API calls should require `X-Operator-Token`.
- `ENFORCE_LOCALHOST_ONLY=true` is the safe default for the local operator API.
- One test account that can receive OTP.
- Test media files only; avoid valuable/private media during validation.

Proxy notes:

- Proxy check is a technical connectivity check, not a profile operation.
- Proxy password storage uses Fernet encryption and requires `PROXY_CREDENTIALS_ENCRYPTION_KEY`.
- Do not print or commit `.env`, `backend/.env`, proxy keys, or local logs.

Windows Redis preference:

- Use portable Memurai at `C:\Tools\Memurai` on this workstation.
- Do not use WSL Redis for this project; it has caused localhost/port instability.
- Docker Compose remains a portable option for PostgreSQL + Redis, but is not required here.

## Recommended Startup

From repo root:

```powershell
.\scripts\start-dev.ps1
```

The launcher starts the local stack without opening a browser by default. Use `-OpenBrowser` if you want it to open the dashboard URL after startup.

This should start:

- Memurai Redis;
- backend API;
- RQ workers;
- Vite frontend.

If doing manual startup, use this order:

1. PostgreSQL
2. Redis/Memurai
3. backend API
4. RQ workers
5. frontend
6. live preflight
7. auth/runtime validation
8. account update validation

## Environment Variables

Use variables instead of hardcoded local paths:

```powershell
$RepoRoot = "C:\Users\user\Documents\workspace-codex\StylistTG"
$ApiBaseUrl = "http://127.0.0.1:<actual-port-from-startup-output>"

cd "$RepoRoot\backend"
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
$env:TDLIB_DATABASE_ROOT="$RepoRoot\backend\tdlib\database"
$env:TDLIB_FILES_ROOT="$RepoRoot\backend\tdlib\files"
$env:TDLIB_SHARED_LIBRARY_PATH="C:\path\to\tdjson.dll"
$env:PROFILE_EXECUTION_ADAPTER="tdlib"
```

Optional story live publishing:

```powershell
$env:STORIES_TDLIB_LIVE_ENABLED="true"
```

Do not enable story live publishing casually. Platform limits are real.

Apply migrations:

```powershell
python -m alembic upgrade head
```

## Start API Manually

From repo root:

```powershell
.\scripts\start_backend.ps1
```

Check the script output for the actual API port. Dashboard local development usually uses `8002`; older live-validation helper flows may use `8000`.

## Start Worker Manually

In a second shell:

```powershell
.\scripts\start_worker.ps1
```

For normal development, prefer two separate workers:

```powershell
cd "$RepoRoot\backend"
python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
```

Workers must use the same Redis URL as API.

If jobs stay queued, verify:

- Redis is reachable;
- profile worker listens to `profile_jobs`;
- auth worker listens to `auth_jobs`;
- API and worker use the same `REDIS_URL`.

## Read-only TDLib Proxy Smoke Plan

Run only with explicit operator approval, because it opens an existing TDLib session. It must not perform write actions.

Expected call order:

```text
setTdlibParameters -> addProxy -> enableProxy -> getMe
```

Validation target:

- saved account proxy is applied before the first read query;
- `getMe` succeeds through the proxy;
- no auth start, code/password submission, profile write, upload, story post, or delete query is sent.

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

Use `$ApiBaseUrl` from startup output:

```powershell
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/health"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/ready"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/diagnostics/runtime"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/diagnostics/live-preflight"
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

After the code arrives:

```powershell
.\scripts\live_auth_flow.ps1 -PhoneNumber "+15550102000" -AccountId "<account-id>" -Code "<otp-code>"
```

Expected after success:

- `authorized_ready` or `execution_usable`;
- `telegram_user_id` set;
- `authorized_last_confirmed_at` present.

If 2FA is requested, use the app UI or auth password endpoint flow.

## Refresh Runtime

```powershell
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/accounts/<account-id>/refresh-runtime"
Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/accounts/<account-id>/runtime-diagnostics"
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
- remember account limits.

Common platform limit errors:

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

If music upload/apply fails, inspect uploaded asset metadata, captured job JSON, step JSON, and the worker log excerpt approved for review.

## Story Deletion Validation

Delete known active story:

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "$ApiBaseUrl/api/story-posts/<story-post-id>" `
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
- approved worker log excerpt.

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
- story error: platform story limit or live story publishing disabled.
- music error: unsupported format or TDLib upload/file-id failure.

## Troubleshooting Notes

- If TDLib reaches `authorizationStateClosed`, do not reuse that client instance.
- If Redis is down, API may still answer `/health`, but `/ready` must be degraded.
- If PostgreSQL is down, `/ready` must be degraded.
- If jobs remain queued, verify worker process and Redis URL.
- If an operation fails, inspect the step result first; do not mask the error as success.
