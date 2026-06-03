# Account Onboarding Runbook

## Operator Notes

- Live TDLib is disabled by default and must remain explicitly gated.
- Session artifacts are private backend-only material. Do not expose raw object keys, TDLib paths, session bytes, OTP, 2FA passwords, API hash, or proxy passwords.
- Imported sessions require readonly verification before any account is marked ready/execution usable.
- Unsupported formats are not silently attached.
- No anti-ban or safety guarantees are implied by onboarding success.
- Audit/event payloads must stay safe and redacted.

## Normal Flow

1. User opens `/accounts/add`.
2. User selects source type and enters phones, JSON metadata, or uploads a private artifact.
3. Frontend creates an onboarding batch and asks backend to validate.
4. Backend returns preview with safe hints, capability support level, risk, validation messages, and next actions.
5. User confirms with `ADD_ACCOUNTS` consent.
6. Backend records consent, queues item jobs, and returns a polling hint.
7. Workers process items and update PostgreSQL final state.
8. Frontend polls batch detail until terminal state.

## Troubleshooting

- `ONBOARDING_CONSENT_REQUIRED`: confirm request did not include accepted `ADD_ACCOUNTS` consent or worker found missing consent.
- `ONBOARDING_QUEUE_UNAVAILABLE`: Redis/RQ enqueue failed. Verify `auth_jobs` worker and Redis.
- `ONBOARDING_ARTIFACT_UNSAFE`: inspect safe `validation_code`; do not bypass quarantine validation.
- `ONBOARDING_RATE_LIMITED`: retry was attempted before `next_retry_at`; wait for `retry_after_seconds`.
- `requires_reauth`: source can be previewed but does not produce a verified ready session.
- `tdlib_not_configured`: TDLib verification cannot run in current environment.

## Cleanup

Artifacts have `expires_at`; the `account_onboarding.artifacts.expire` maintenance workflow marks expired private artifact metadata as `expired`. Physical disposal must remain conservative and must not delete live TDLib storage unless the materialization record proves it belongs to the onboarding artifact.
