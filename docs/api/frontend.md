# Frontend API

This document defines the current frontend/backend contract for StylistTG.

The frontend is polling-first:

1. load account list or dashboard payload;
2. upload assets when the user selects photo/audio/story media;
3. build a non-mutating preview;
4. create a queued job;
5. poll latest job, job detail, and ordered step results;
6. refresh dashboard after terminal job state.

There is no WebSocket/SSE contract.

Frontend route/query architecture is documented in `docs/architecture/frontend-saas-foundation.md`.

Mutating local operator endpoints may require `X-Operator-Token` when `OPERATOR_API_TOKEN` is configured. The backend defaults to localhost-only access for operator safety. The browser UI does not store or send `OPERATOR_API_TOKEN`; use it only for API/reverse-proxy clients.

SaaS boundary:

- FastAPI is the only data access layer.
- Neon is the PostgreSQL provider.
- Supabase is the auth provider only; frontend must not access database tables directly.
- In `AUTH_MODE=supabase_jwt`, frontend sends `Authorization: Bearer <Supabase JWT>` and optionally `X-Workspace-Id`.
- Backend maps JWT users to local `app_user` rows and enforces workspace membership/roles.

Canonical frontend routes are:

- `/` -> `/home`
- `/home`
- `/accounts`
- `/accounts/add`
- `/accounts/$accountId/profile`
- `/accounts/$accountId/stories`
- `/accounts/$accountId/music`
- `/accounts/$accountId/proxy`
- `/accounts/$accountId/jobs`
- `/accounts/$accountId/risk`
- `/health`
- `/jobs`
- `/modules/warmup`
- `/settings`
- `/proxy`
- `/billing`

Compatibility routes:

- `/auth/batch`
- `/operations`

Legacy query URLs are compatibility redirects only.

## Error DTO

All structured API errors use this shape:

```json
{
  "error_code": "ACCOUNT_NOT_FOUND",
  "error_class": "not_found",
  "message": "account not found",
  "details": null,
  "field_errors": [],
  "request_id": "0f0b7304-e22a-4fec-9ef1-d1b5c5c4f1f4"
}
```

Fields:

- `error_code`: stable UI-facing code, translated in `apps/dashboard/src/lib/uiLabels.ts`;
- `error_class`: broad error bucket;
- `message`: operator-readable message;
- `details`: optional structured data;
- `field_errors`: field-level validation problems;
- `request_id`: correlation id for logs/support.

## Runtime and Diagnostics

### GET /health

Process liveness. It may return `200` even when Redis is down.

### GET /ready

Readiness. Returns `200` only when DB and Redis are OK. Returns `503` when either is unavailable.

### GET /diagnostics/runtime

Structured runtime diagnostics for Settings UI.

### GET /diagnostics/live-preflight

Structured live readiness diagnostics for TDLib, storage, DB, Redis, tooling checks, and separate `profile_jobs` / `auth_jobs` worker statuses. `rq_worker_status` remains a compatibility summary.

## Accounts

### GET /api/accounts

Returns accounts for the account list.

Frontend type:

```ts
type AccountListItem = {
  account_id: string
  display_name: string | null
  username: string | null
  phone_number: string
  telegram_user_id: string | null
  account_state: string
  runtime_health: string
  is_execution_usable: boolean
  is_test_dc: boolean
  profile_photo_asset_id: string | null
  updated_at: string
}
```

### DELETE /api/accounts/{account_id}

Deletes an account record from the app.

### POST /api/accounts/refresh-runtime

Uses `X-Account-Id` header.

Refreshes runtime usability for the selected account.

### GET /api/accounts/runtime-diagnostics

Uses `X-Account-Id` header.

Returns compact account-level runtime diagnostics.

### GET /api/accounts/safety-summary

Returns compact account safety/readiness summaries for the account list. Includes health, risk, validity, cooldown summary, top reasons, and `proxy_status`.

### GET /api/accounts/{account_id}/safety

Returns full safety matrix for an account: capabilities, risk by operation, cooldowns, reasons, latest validity check, and proxy status.

### POST /api/accounts/{account_id}/validity-check

Runs a safe validity check. `tdlib_readonly` may connect to an existing TDLib session but must not submit auth codes/passwords or perform Telegram write actions.

### GET /api/accounts/{account_id}/validity-checks

Returns recent validity-check history for the account.

### POST /api/accounts/{account_id}/safety-overrides

Stores an audited manual safety review for overridable blockers. Non-overridable blockers remain protected.

### GET /api/accounts/proxy-summary

Returns compact proxy status by account for the account list. The response never includes proxy passwords.

Proxy status values:

- `unknown`: no successful check yet;
- `tcp_working`: TCP proxy connection works, Telegram through proxy was not verified;
- `tdlib_working`: read-only TDLib verification through proxy succeeded;
- `tdlib_unverified`: TCP works, but the account is not ready for Telegram verification;
- `failed`: TCP proxy check failed;
- `tdlib_failed`: TDLib/proxy runtime verification failed.

### GET /api/accounts/{account_id}/proxy

Returns account proxy configuration/status. Password is never returned; frontend receives `has_password`.

### PUT /api/accounts/{account_id}/proxy

Creates or updates account proxy settings. Proxy passwords require backend `PROXY_CREDENTIALS_ENCRYPTION_KEY`; without it, password save is rejected.

### DELETE /api/accounts/{account_id}/proxy

Removes proxy assignment for the account.

### POST /api/accounts/{account_id}/proxy/check

Runs a technical proxy connectivity check and updates proxy status. In TDLib live mode with configured TDLib credentials, the backend also performs a read-only TDLib validity check through the saved proxy. This is diagnostics only and does not perform Telegram account writes. Account readiness problems such as `reauth_required` are represented as `tdlib_unverified`, not as TCP proxy failure.

### GET /api/accounts/{account_id}/operation-logs

Returns paginated operation logs for one account.

### GET /api/operation-logs

Returns paginated global operation logs across accounts.

## Dashboard

### GET /api/dashboard/profile

Uses `X-Account-Id` header.

Aggregated payload for the authenticated profile editor.

Important payload sections:

- `account`: account identity and runtime state;
- `current_profile`: materialized current profile state;
- `profile_audio`: known profile music state;
- `story_posts`: active story posts known to the app;
- `editable_fields`: form bootstrap values;
- `pipeline`: latest job state;
- `diagnostics`: last known runtime/auth diagnostics.

Important states:

- `current_profile.*` may be `null` if backend has no safe local knowledge.
- `is_execution_usable=false` means UI should block job creation and offer runtime refresh.
- `story_posts` contains only stories known/synced by the app, not a guaranteed full Telegram archive.

## Assets

### POST /api/assets/profile-photo

Uploads a profile photo asset.

### POST /api/assets/profile-audio

Uploads profile music. Execution supports MP3/M4A.

### POST /api/assets/story-image

Uploads story image media.

### POST /api/assets/story-video

Uploads story video media.

### GET /api/assets/{asset_id}

Returns asset metadata.

### GET /api/assets/{asset_id}/content

Returns asset file content for previews.

## Main Account Update Workflow

Use this workflow for profile text, avatar, profile music, and stories.

### POST /api/account-update/preview

Builds a non-mutating execution preview.

Request:

```json
{
  "account_id": "account-1",
  "profile": {
    "name": "Alice Example",
    "bio": "Profile editor",
    "username": "alice_example",
    "photo_asset_id": "asset-photo-1"
  },
  "profile_audio": {
    "action": "add",
    "audio_asset_id": "asset-audio-1"
  },
  "stories": [
    {
      "client_id": "story-1",
      "action": "post_video",
      "asset_id": "asset-video-1",
      "caption": "Hello",
      "privacy_preset": "contacts",
      "active_period_seconds": 86400,
      "protect_content": false
    }
  ]
}
```

Response:

```json
{
  "can_create_job": true,
  "blocking_errors": [],
  "warnings": [],
  "normalized_payload": {
    "name": "Alice Example",
    "bio": "Profile editor",
    "username": "alice_example",
    "photo_asset_id": "asset-photo-1"
  },
  "desired_state_normalized": {},
  "execution_intent_hash": "abc123",
  "workflow_type": "account_update",
  "workflow_version": 1,
  "capability_snapshot": {},
  "plan_json_snapshot": {
    "steps": []
  },
  "steps": [],
  "requires_execution_usable": true,
  "dedup_would_block": false,
  "dedup_blocked_by_job_id": null
}
```

Possible step types:

- `set_name`
- `set_bio`
- `set_username`
- `set_profile_photo`
- `upload_profile_audio`
- `add_profile_audio`
- `remove_profile_audio`
- `story_N_validate_capabilities`
- `story_N_prepare_media`
- `story_N_post`

Important states:

- Preview never enqueues a job.
- `can_create_job=false` means UI must not create a job.
- `blocking_errors` should be translated through `apps/dashboard/src/lib/uiLabels.ts`.

### POST /api/account-update/jobs

Creates and enqueues an account update job.

Request shape is the same as preview.

Successful response:

```json
{
  "job_id": "job-1",
  "job_state": "queued",
  "execution_intent_hash": "abc123",
  "plan_summary": ["set_name", "upload_profile_audio", "add_profile_audio"],
  "created_at": "2026-04-29T12:00:00Z",
  "dedup_blocked_by_job_id": null,
  "message": null
}
```

Possible errors:

- `ACCOUNT_NOT_FOUND`
- `RUNTIME_UNUSABLE`
- `VALIDATION_ERROR`
- `PROFILE_AUDIO_UNSUPPORTED_FORMAT`
- `PROFILE_JOB_COOLDOWN_ACTIVE`
- `STORIES_DISABLED`
- `STORIES_TDLIB_LIVE_DISABLED`
- `STORY_ASSET_NOT_READY`
- `QUEUE_UNAVAILABLE`

## Legacy Profile Job Workflow

Still present for compatibility:

- `POST /api/jobs/profile/preview`
- `POST /api/jobs/profile`

Use `/api/account-update/*` for new UI work because it supports profile audio and stories.

## Job Polling

### GET /api/accounts/jobs/latest

Uses `X-Account-Id` header.

Returns latest job summary.

### GET /api/accounts/jobs?limit=10

Uses `X-Account-Id` header.

Returns recent job summaries.

### GET /api/jobs/{job_id}

Returns detailed job state and step counts.

### GET /api/jobs/{job_id}/steps

Returns ordered persisted step results.

Important states:

- Steps are returned in plan order.
- Steps with no persisted result may be omitted.
- Frontend should combine preview plan + persisted steps to show planned/not-started items.

## Story Drafts and Posts

### GET /api/story-drafts

Uses `X-Account-Id` header.

Returns saved story drafts for the current account.

### POST /api/story-drafts

Creates a story draft.

### PATCH /api/story-drafts/{draft_id}

Updates caption/privacy/protect settings.

### DELETE /api/story-drafts/{draft_id}

Deletes a draft. Frontend treats `STORY_DRAFT_NOT_FOUND` as already deleted.

### GET /api/story-capabilities

Uses `X-Account-Id` header.

Returns story capability metadata:

- whether stories are enabled;
- whether TDLib live publishing is enabled;
- allowed privacy presets;
- max caption length;
- ffmpeg/ffprobe availability;
- warnings.

### DELETE /api/story-posts/{story_post_id}

Uses `X-Account-Id` header.

Deletes an active story known to the app.

Possible errors:

- `STORY_POST_NOT_FOUND`
- `STORY_POST_CANNOT_DELETE`
- `STORY_DELETE_FAILED`

## Batch Auth

### POST /api/auth-batches/validate-phones

Validates phone numbers before creating a batch.

Returns:

- `valid_items`
- `invalid_items`
- `duplicates`
- `existing_accounts`
- `active_batch_conflicts`

### POST /api/auth-batches

Creates a batch auth session.

### POST /api/auth-batches/{batch_id}/start

Starts batch execution.

### GET /api/auth-batches/{batch_id}

Returns current batch snapshot.

### GET /api/auth-batches/{batch_id}/poll

Polling endpoint for batch changes.

### POST /api/auth-batches/{batch_id}/pause
### POST /api/auth-batches/{batch_id}/resume
### POST /api/auth-batches/{batch_id}/cancel

Batch controls.

### POST /api/auth-batches/{batch_id}/items/{item_id}/submit-code
### POST /api/auth-batches/{batch_id}/items/{item_id}/submit-2fa
### POST /api/auth-batches/{batch_id}/items/{item_id}/retry
### POST /api/auth-batches/{batch_id}/items/{item_id}/request-new-code
### POST /api/auth-batches/{batch_id}/items/{item_id}/cancel

Item-level controls.

## Settings

### GET /api/settings/execution-policy

Returns execution cooldown policy.

### PATCH /api/settings/execution-policy

Updates cooldown policy.

## Auth Runtime Mode

### GET /api/auth/runtime-mode
### PATCH /api/auth/runtime-mode

Controls normal Telegram vs Test DC.

Important:

- Test DC is an advanced/development mode.
- Ordinary Telegram accounts do not authorize in Test DC.
- Batch form should switch Test DC without redirecting to the legacy single-auth screen.

## Frontend URL Contract

Canonical frontend routes:

- `/` -> `/home`
- `/home`
- `/accounts`
- `/accounts/add`
- `/settings`
- `/accounts/$accountId`
- `/accounts/$accountId/profile`
- `/accounts/$accountId/jobs`
- `/accounts/$accountId/stories`
- `/accounts/$accountId/music`
- `/accounts/$accountId/proxy`
- `/accounts/$accountId/risk`
- `/accounts/$accountId/debug`
- `/health`
- `/jobs`
- `/modules/warmup`
- `/proxy`
- `/billing`

Compatibility routes:

- `/auth/batch`
- `/operations`

Legacy query URLs are compatibility redirects only:

- `/?view=settings` -> `/settings`
- `/?view=auth-batch` -> `/auth/batch`
- `/?account_id=<id>` -> `/accounts/<id>`

Route components are code-split at product boundaries through TanStack Router:

- accounts/settings route area
- batch auth route
- warmup route
- account workspace route

Account workspace routes must keep loader-first behavior: frontend should resolve `authState` and
`dashboardBundle` through `apps/dashboard/src/lib/queries.ts` before rendering the editor. This prevents warm
navigation from briefly showing skeleton/auth fallback screens.

## Polling Model

Recommended account update polling flow:

1. `GET /api/dashboard/profile`
2. upload selected assets
3. `POST /api/account-update/preview`
4. `POST /api/account-update/jobs`
5. poll `GET /api/accounts/jobs/latest`
6. poll `GET /api/jobs/{job_id}`
7. poll `GET /api/jobs/{job_id}/steps`
8. when terminal, refresh `GET /api/dashboard/profile`
