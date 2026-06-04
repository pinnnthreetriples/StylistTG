# Account Onboarding Architecture

Account Onboarding is the canonical account-addition bounded context. `/accounts/add` should use this flow instead of composing legacy `AuthBatch`, `AccountImportBatch`, and `TelegramAuthSession` screens.

## Flow

```text
React Add Accounts Wizard
-> typed API client
-> FastAPI account_onboarding router
-> account_onboarding service/state machine
-> PostgreSQL source of truth
-> RQ auth_jobs worker execution
-> source adapters / TDLib verification
-> PostgreSQL final state
-> frontend polling
```

PostgreSQL owns batch, item, artifact, and event truth. Redis/RQ is execution infrastructure only. The frontend is UI/orchestration only and never receives raw session data, TDLib paths, OTP, 2FA passwords, API hash, or proxy passwords.

## Data Model

Tables:

- `account_onboarding_batch`: workspace-scoped batch intent, source type, status, consent fields, counters, timestamps, failure summary, and create idempotency metadata.
- `account_onboarding_item`: workspace-scoped per-account item with safe hints, validation result, risk, reauth marker, retry count, and optional account/auth/artifact links.
- `account_onboarding_artifact`: private backend-only upload metadata with object key, hash, size, content type, lifecycle, expiry, and failure summary.
- `account_onboarding_event`: append-only safe event stream with redacted payloads.

All lookups must include `workspace_id`. Frontend responses expose ids, statuses, counters, safe hints, validation messages, risk, next action, and polling hints only.

## State Machine

Batch statuses:

`created`, `uploaded`, `validating`, `preview_ready`, `confirmed`, `queued`, `running`, `partially_completed`, `completed`, `requires_reauth`, `failed`, `cancelled`, `expired`.

Item statuses:

`pending`, `validating`, `valid`, `duplicate`, `existing`, `unsupported`, `blocked`, `requires_reauth`, `queued`, `starting_auth`, `waiting_code`, `waiting_2fa`, `importing_session`, `checking_session`, `ready`, `failed`, `cancelled`.

Status changes must go through `backend/app/modules/account_onboarding/state.py`, which validates transitions, updates timestamps/counters, and writes safe events.

## Source Adapters

Capability levels are exposed to the wizard:

| Source | Support | Notes |
| --- | --- | --- |
| `phone` / `phone_bulk` | `full` | One phone and many phones are the same batch flow. Phone preview validates normalization, duplicates, existing accounts, and active conflicts. After consent, Account Onboarding creates an internal `AuthBatch`, starts the existing TDLib authorization worker path, and mirrors `waiting_code`, `waiting_2fa`, and `ready` back onto onboarding items. Raw phone numbers and auth batch links stay backend-only. |
| `json_metadata` | `requires_reauth` | Metadata preview only. It never creates an execution-usable session or claims `session_present=true`. |
| `tdlib_directory` | `preview_only` until imported-artifact materialization and readonly verification are wired | Requires private artifact, quarantine validation, isolated materialization, then readonly verification before readiness. It must not be displayed as full support until the backend can actually verify imported TDLib material. |
| `tdata_archive` | `requires_reauth` | Full tdata conversion/materialization is not implemented in the foundation path. The UI must present it as reauth/manual work until a verified converter exists. |
| `session_file` | `preview_only` | Only explicitly whitelisted preview formats may be inspected. Unknown formats are unsupported/requires reauth and are never silently materialized or attached. |

## Artifact Security

Artifacts are uploaded through `/api/account-onboarding-artifacts` and stored under backend private storage. Responses never include object keys or public/signed URLs.

Archive validation rejects:

- empty or invalid archives;
- absolute paths;
- `..` traversal;
- symlinks;
- excessive file count;
- excessive depth;
- excessive uncompressed size.

Artifacts are not unpacked into TDLib storage during upload. TDLib materialization must use quarantine -> isolated backend-only storage -> readonly verification.

Physical artifact cleanup is a separate maintenance workflow. It may delete bytes only for expired, cancelled, or rejected onboarding artifacts whose `object_key` stays inside the backend-private `account-onboarding/` namespace. Cleanup must not delete final TDLib live storage, must not expose object keys or filesystem paths, and records only safe event metadata.

## Consent Gate

Preview/validation can run without consent. Confirming a batch requires:

```json
{
  "confirmation": "ADD_ACCOUNTS",
  "consent_accepted": true,
  "consent_version": "account-onboarding-v1"
}
```

The backend stores `consent_confirmed_at`, `consent_actor_user_id`, and `consent_version`. Worker execution must reject live account addition/session materialization if consent is missing.

## Worker Execution

Confirm stores intent and queues item jobs on `auth_jobs`; it does not run long TDLib work synchronously. For phone onboarding, item execution delegates to the existing `AuthBatch` TDLib worker path and polling syncs the linked auth item state back into the onboarding snapshot. Worker payloads contain item ids, not raw OTP/2FA/session bytes. Final state is written back to PostgreSQL.

Queue unavailable must be surfaced safely through `ONBOARDING_QUEUE_UNAVAILABLE` and non-secret failure state.

Retries are bounded. Retry decisions use the shared retry policy categories, set `next_retry_at` for cooldown-aware attempts, and must never loop indefinitely.

## Legacy Migration

Legacy surfaces remain compatibility-only while `/accounts/add` becomes the canonical foundation and preview entrypoint:

- `AuthBatch`: live phone authorization remains the execution engine; Account Onboarding owns the `/accounts/add` UX and delegates phone items to internal auth batches after consent.
- `AccountImportBatch`: import preview behavior migrates into source adapters and artifact pipeline.
- `TelegramAuthSession` / OTP routes: remain compatibility routes and reauth primitives, not independent add-account UI flows.

Do not add new independent live add-account flows.
