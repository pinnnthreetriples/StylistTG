# Account Update Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current profile-only backend job shape with a professional unified account update workflow: one user-facing "Create task" action produces one durable `AccountUpdateJob`, and the backend orchestrates typed steps for profile fields, profile photo, profile music, and future stories.

**Architecture:** The backend uses an orchestration/saga-style workflow. A versioned desired-state payload is converted into a versioned execution plan. The plan is executed by typed step handlers through a registry, with durable step results, retry/compensation policy, capability checks, readback verification, and materialized state updates.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, RQ/Redis, TDLib JSON, Pydantic, pytest, ruff. Frontend integration comes after backend contract is stable.

---

## 0. Design Intent

The user sees one action:

```text
Create task
```

The backend receives one desired state:

```json
{
  "account_id": "account-1",
  "profile": {
    "name": "King",
    "bio": "Bio",
    "username": "king",
    "photo_asset_id": "asset-photo"
  },
  "profile_audio": {
    "action": "add",
    "audio_asset_id": "asset-audio"
  },
  "stories": []
}
```

The backend builds one plan:

```json
{
  "workflow_type": "account_update",
  "workflow_version": 1,
  "steps": [
    { "step_type": "set_name" },
    { "step_type": "set_bio" },
    { "step_type": "set_username" },
    { "step_type": "set_profile_photo" },
    { "step_type": "add_profile_audio" }
  ]
}
```

This is not a single giant profile operation. It is one durable workflow made of typed steps.

---

## 1. Non-Negotiable Architecture Rules

- Keep one user-facing job creation flow.
- Do not add music or stories as ad hoc fields inside the old `ProfileJobCreate`.
- Preserve backward compatibility for current profile UI until frontend migrates.
- Every step type must declare:
  - handler name
  - capability requirement
  - retry policy
  - compensation policy
  - materialization behavior
  - verification behavior
- A workflow can be partially successful, but it must be explicit and explainable.
- External TDLib side effects are never assumed atomic with DB writes.
- Materialized state is updated only after readback or trusted success.
- Stories are designed into the model now, but not fully implemented in the first backend coding pass.

---

## 2. Target Backend Shape

### Workflow Types

Initial:

```text
account_update
```

Optional compatibility:

```text
profile_update
```

If possible, map old profile jobs into `account_update` internally instead of keeping two execution engines.

### Step Types

Current profile steps:

```text
set_name
set_bio
set_username
set_profile_photo
```

Music steps:

```text
upload_profile_audio
add_profile_audio
remove_profile_audio
sync_profile_audio
```

Future story steps:

```text
prepare_story_image
post_story_image
prepare_story_video
post_story_video
sync_story_post_result
delete_story
```

Stories are registered as reserved/future step types in code comments/docs, but production handlers can remain disabled behind feature flags until their phase.

---

## 3. Data Model

### Jobs Table Evolution

Modify `backend/app/models.py` and migration:

```text
jobs.workflow_type          string, default "profile_update" or "account_update"
jobs.workflow_version       int, default 1
jobs.desired_state_json     json nullable during compatibility phase
jobs.capability_snapshot_json json nullable
jobs.compensation_state     string nullable
```

Keep existing fields:

```text
payload_json
plan_json_snapshot
execution_intent_hash
job_state
```

Reason: current code and tests depend on them. We evolve, not rewrite in one risky cut.

### Step Results Evolution

Current `JobStepResult` is mostly enough. Add only if needed:

```text
job_step_results.step_order int nullable
job_step_results.compensation_status string nullable
job_step_results.capability_key string nullable
job_step_results.retry_count int default 0
```

### Materialized State

Keep:

```text
account_profile_state
```

Add:

```text
account_profile_audio_state
```

Suggested fields:

```text
account_id
telegram_audio_id nullable
telegram_file_id nullable
title nullable
performer nullable
duration_seconds nullable
mime nullable
source_asset_id nullable
raw_tdlib_json json
synced_at
```

Future:

```text
account_story_state
```

Do not create story table until story implementation begins unless migration timing favors it.

---

## 4. Backend Modules

### New Modules

Create:

```text
backend/app/services/account_update_desired_state.py
backend/app/services/account_update_plan.py
backend/app/services/account_update_orchestrator.py
backend/app/services/step_registry.py
backend/app/services/step_policies.py
backend/app/services/profile_audio_state.py
backend/app/services/profile_audio_assets.py
backend/app/adapters/tdlib_profile_audio.py
backend/app/workers/account_update_jobs.py
backend/app/api/account_update.py
```

### Existing Modules To Modify

Modify:

```text
backend/app/models.py
backend/app/schemas.py
backend/app/main.py
backend/app/api/jobs.py
backend/app/api/dashboard.py
backend/app/services/dashboard.py
backend/app/services/plan.py
backend/app/adapters/tdlib_profile_execution.py
backend/app/workers/profile_jobs.py
backend/app/job_queue/rq.py
```

### Compatibility Strategy

Existing endpoint:

```text
POST /api/jobs/profile
POST /api/jobs/profile/preview
```

Should continue to work. Internally it can call the new account-update plan builder with:

```json
{
  "profile": {
    "name": "...",
    "bio": "...",
    "username": "...",
    "photo_asset_id": "..."
  },
  "profile_audio": { "action": "keep" },
  "stories": []
}
```

New endpoint:

```text
POST /api/account-update/preview
POST /api/account-update/jobs
```

Frontend migrates to the new endpoint later.

---

## 5. Desired State Contract

Create Pydantic schemas:

```python
class AccountUpdateProfileDesiredState(BaseModel):
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None

class ProfileAudioAction(str, Enum):
    keep = "keep"
    add = "add"
    remove = "remove"

class AccountUpdateProfileAudioDesiredState(BaseModel):
    action: ProfileAudioAction = ProfileAudioAction.keep
    audio_asset_id: str | None = None

class AccountUpdateStoryDesiredState(BaseModel):
    action: Literal["post_image", "post_video"]
    asset_id: str
    caption: str | None = None
    privacy_preset: str = "contacts"
    active_period_seconds: int = 86400

class AccountUpdateCreate(BaseModel):
    account_id: str
    profile: AccountUpdateProfileDesiredState | None = None
    profile_audio: AccountUpdateProfileAudioDesiredState | None = None
    stories: list[AccountUpdateStoryDesiredState] = []
```

Validation rules:

- `profile_audio.action == "add"` requires `audio_asset_id`.
- `profile_audio.action == "remove"` ignores `audio_asset_id`.
- stories are rejected unless `stories_enabled` is true.
- unsupported story actions return structured validation errors.

---

## 6. Plan Builder

Create `build_account_update_plan(account_id, desired_state, current_state, capabilities)`.

Output:

```python
{
    "workflow_type": "account_update",
    "workflow_version": 1,
    "job_payload_version": 2,
    "steps": [
        {
            "step_key": "set_name",
            "step_type": "set_name",
            "order": 1,
            "required": True,
            "capability_key": "profile_text",
            "retry_policy": "standard",
            "compensation_policy": "restore_previous_value",
            "idempotency_class": "profile_field_replace",
            "payload": {...},
        }
    ],
}
```

Ordering:

1. `set_name`
2. `set_bio`
3. `set_username`
4. `set_profile_photo`
5. `upload_profile_audio`
6. `add_profile_audio`
7. story preparation steps
8. story post steps
9. sync/materialization steps if needed

Music ordering rationale:

- `upload_profile_audio` happens before `add_profile_audio`.
- `add_profile_audio` is a pivot-like external side effect.
- If later stories fail, audio may be compensatable by `remove_profile_audio`, but only if user selected "all-or-nothing" mode in the future. Initial behavior should be partial-success, not automatic destructive rollback.

---

## 7. Step Registry

Create a registry:

```python
class StepHandler(Protocol):
    step_type: str

    def execute(self, context: StepExecutionContext, step: dict[str, Any]) -> StepExecutionResult:
        ...

    def compensate(self, context: StepExecutionContext, step: dict[str, Any]) -> StepCompensationResult:
        ...
```

Initial handlers:

```text
SetNameStepHandler
SetBioStepHandler
SetUsernameStepHandler
SetProfilePhotoStepHandler
UploadProfileAudioStepHandler
AddProfileAudioStepHandler
RemoveProfileAudioStepHandler
```

Future disabled handlers:

```text
PostStoryImageStepHandler
PostStoryVideoStepHandler
DeleteStoryStepHandler
```

Important: step registry must make it impossible to silently ignore unknown step types. Unknown step type fails job with `UNSUPPORTED_STEP_TYPE`.

---

## 8. Execution Semantics

Use one orchestrator:

```text
account_update_orchestrator.execute(job_id)
```

For each step:

1. Write `step_started`.
2. Execute handler.
3. Write `step_succeeded`, `step_failed`, or `step_uncertain`.
4. If hard failure:
   - stop remaining required steps.
   - mark job failed or partially completed depending on completed side effects.
5. If uncertain:
   - stop if policy says manual intervention.
   - otherwise continue only for independent steps.
6. At end:
   - read back materialized state.
   - mark job completed or partially completed.

Do not hide partial success.

Job state mapping:

```text
completed
partially_completed
failed
manual_intervention_needed
dedup_blocked
```

---

## 9. Compensation Policy

Do not implement aggressive automatic rollback in the first orchestrator version.

Add policy metadata now:

```text
none
restore_previous_value
remove_added_audio
delete_posted_story
manual_only
```

Initial runtime behavior:

- record compensation policy in plan.
- do not auto-compensate unless step handler is explicitly marked safe and feature flag `account_update_auto_compensation_enabled` is true.

Why:

- Telegram side effects are user-visible.
- Username rollback can fail.
- Stories can be seen before deletion.
- Automatic rollback can surprise users more than partial-success reporting.

---

## 10. Capability Model

Add capability snapshot per job:

```json
{
  "profile_text": "true",
  "profile_photo": "true",
  "profile_audio": "unknown",
  "stories_image": "false",
  "stories_video": "false"
}
```

Capability values:

```text
true
false
unknown
```

Rules:

- `false` blocks preview/job creation for required steps.
- `unknown` allows preview with warning, but job creation may be blocked depending on step risk.
- music can start as `unknown` until TDLib spike validates it.
- stories should be `false` until feature flag and TDLib spike are complete.

---

## 11. Profile Audio Integration

### Asset Pipeline

Add:

```text
POST /api/assets/profile-audio
```

Validate:

- non-empty file
- MIME allowlist
- max bytes
- max duration
- decodable metadata

Store:

- original file
- normalized file only if normalization is implemented
- metadata

### TDLib Audio Adapter

Create adapter methods:

```python
fetch_current_profile_audio(account_id) -> dict | None
upload_profile_audio(account_id, asset_path) -> dict
add_profile_audio(account_id, file_id) -> dict
remove_profile_audio(account_id, audio_id_or_file_id) -> dict
```

Exact TDLib remove query must be confirmed by spike before final coding.

### Materialization

After `add_profile_audio`:

- read `userFullInfo.first_profile_audio`.
- upsert `account_profile_audio_state`.

After `remove_profile_audio`:

- read back.
- clear or update `account_profile_audio_state`.

---

## 12. Stories Future-Proofing

Do not implement story posting in the music backend pass, but reserve the architecture.

Stories need:

- own asset kinds:
  - `story_image`
  - `story_video`
- own capability keys:
  - `stories_image`
  - `stories_video`
  - `stories_caption_entities`
  - `stories_url_areas`
- own failure listener:
  - `updateStoryPostFailed`
- own materialized state:
  - story id
  - local job id
  - post status
  - failure payload

Plan builder should reject non-empty `stories` with:

```text
STORIES_DISABLED
```

until story feature flag is enabled.

---

## 13. API Contract

New preview:

```text
POST /api/account-update/preview
```

Returns:

```json
{
  "can_create_job": true,
  "blocking_errors": [],
  "warnings": [],
  "execution_intent_hash": "...",
  "workflow_type": "account_update",
  "workflow_version": 1,
  "desired_state_normalized": {},
  "capability_snapshot": {},
  "plan_json_snapshot": {},
  "steps": []
}
```

New create:

```text
POST /api/account-update/jobs
```

Returns existing `JobSummaryRead` shape plus workflow fields if we extend it:

```json
{
  "job_id": "...",
  "job_state": "queued",
  "workflow_type": "account_update",
  "execution_intent_hash": "...",
  "plan_summary": []
}
```

Compatibility:

`POST /api/jobs/profile/preview` and `POST /api/jobs/profile` keep returning current shapes until frontend migrates.

---

## 14. Testing Strategy

### Backend Unit Tests

Add:

```text
backend/tests/test_account_update_desired_state.py
backend/tests/test_account_update_plan.py
backend/tests/test_step_registry.py
backend/tests/test_account_update_orchestrator.py
backend/tests/test_profile_audio_assets.py
backend/tests/test_profile_audio_state.py
backend/tests/test_account_update_api.py
```

### Backend Integration Tests

Add:

```text
backend/tests/test_account_update_profile_compat.py
backend/tests/test_account_update_profile_audio_flow.py
backend/tests/test_dashboard_account_update_contract.py
```

### Live Tests

Add later:

```text
backend/tests/test_profile_audio_live.py
```

Live tests must be skipped unless explicit env vars are present.

---

## 15. Implementation Phases

### Phase 1: Backend Orchestrator Foundation

- [ ] Add job workflow metadata migration.
- [ ] Add account update desired-state schemas.
- [ ] Add account update plan builder for current 4 profile steps only.
- [ ] Add step registry for current 4 profile steps.
- [ ] Add account update preview/create endpoints.
- [ ] Keep old profile endpoints working through compatibility adapter.
- [ ] Add tests proving old and new profile plans are equivalent.

Verification:

```bash
cd backend
python -m pytest backend/tests/test_account_update_plan.py backend/tests/test_account_update_profile_compat.py -q
python -m ruff check .
```

### Phase 2: Orchestrator Worker

- [ ] Add `account_update_jobs.py`.
- [ ] Execute current 4 profile steps through step registry.
- [ ] Keep old worker path until new path is stable.
- [ ] Add durable step result tests.
- [ ] Add partial-success state tests.

Verification:

```bash
cd backend
python -m pytest backend/tests/test_account_update_orchestrator.py -q
```

### Phase 3: Profile Audio Read Model

- [ ] Add `account_profile_audio_state`.
- [ ] Add profile audio schemas.
- [ ] Add read/refresh service.
- [ ] Add dashboard profile audio block.
- [ ] Add tests with fake TDLib adapter.

Verification:

```bash
cd backend
python -m pytest backend/tests/test_profile_audio_state.py backend/tests/test_dashboard_account_update_contract.py -q
```

### Phase 4: Profile Audio Asset Pipeline

- [ ] Add `profile_audio` asset upload endpoint.
- [ ] Add validation and metadata extraction.
- [ ] Add config fields.
- [ ] Add tests for valid/invalid files.

Verification:

```bash
cd backend
python -m pytest backend/tests/test_profile_audio_assets.py -q
```

### Phase 5: Profile Audio Steps In Account Update

- [ ] Add `upload_profile_audio`, `add_profile_audio`, `remove_profile_audio` step handlers.
- [ ] Extend plan builder for `profile_audio`.
- [ ] Extend account update preview/create.
- [ ] Materialize audio state after readback.
- [ ] Add dedup coverage including profile + audio desired state.

Verification:

```bash
cd backend
python -m pytest backend/tests/test_account_update_profile_audio_flow.py -q
```

### Phase 6: TDLib Capability Spike And Live Validation

- [ ] Add spike script for profile audio.
- [ ] Verify exact add/remove/readback behavior on Test DC.
- [ ] Update TDLib adapter with exact query shapes.
- [ ] Add live test behind explicit flags.

Verification:

```bash
cd backend
python -m pytest -m live backend/tests/test_profile_audio_live.py -q
```

### Phase 7: Frontend Migration

- [ ] Add typed frontend account update API.
- [ ] Keep one button "Создать задачу".
- [ ] Include profile + music desired state in one preview/create request.
- [ ] Update dashboard to render audio state.
- [ ] Keep instant tabs and draft preservation.

Verification:

```bash
npm run lint
npm test
npm run build
```

---

## 16. Acceptance Criteria

- One backend job can contain profile text/photo and music steps.
- Current profile-only UI keeps working during migration.
- New account-update endpoint supports current profile operations.
- Profile audio can be added/removed as part of the same account update workflow.
- Job result explains every step independently.
- Partial success is explicit and recoverable.
- Materialized profile/audio state is updated only after readback/trusted success.
- Stories are blocked by feature flag but fit the same desired-state/step-handler model.
- Existing tests pass.

Final verification:

```bash
npm run lint
npm test
npm run build
cd backend && python -m ruff check .
cd backend && python -m pytest -q
```

