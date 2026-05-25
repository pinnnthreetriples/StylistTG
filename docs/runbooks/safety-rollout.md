# Safety Pipeline Rollout

## Pre-flight checklist

- Confirm migrations are applied through `20260520_0047`.
- Confirm the default value for `workspaces.safety_pipeline_v2_enabled` is `false`.
- Confirm safety-policy presets, quarantine, proxy health, and warmup status checks have fresh targeted test coverage.
- Confirm admin access to `PATCH /api/workspaces/{workspace_id}/feature-flags`.
- Confirm monitoring covers safety-gate verdict volume, blocked reasons, queue error rate, and operator overrides.
- Confirm rollback owners and communication channels are assigned before enabling canaries.

## Stage 1 canary 48h

Enable `safety_pipeline_v2_enabled` for a small named canary workspace set for 48 hours.
Watch for unexpected increases in `blocked` verdicts, stale warmup state, false-positive proxy failures,
and account lifecycle support tickets. Do not expand while unresolved regressions are open.

## Stage 2 10% 5 days by id hash

Enable the flag for workspaces whose stable workspace id hash falls into the first 10% bucket.
Hold this stage for 5 days. Compare blocked reason distribution, action throughput, and audit event
volume against the prior 7-day baseline.

## Stage 3 50% 3 days

Expand the id-hash bucket to 50% of workspaces for 3 days. Keep a daily review of false positives,
quarantine volume, and operator override requests. Pause expansion if blocked verdicts or support
load exceed the pre-flight thresholds.

## Stage 4 100%

Enable the flag for all active workspaces after Stage 3 is stable. Keep the feature flag writable
until the legacy shim removal has its own migration and rollback plan.

## Rollback procedure

Set `safety_pipeline_v2_enabled=false` for affected workspaces through the admin feature-flag API.
Verify new safety-gate evaluations return only the legacy shim reasons: `proxy_unhealthy`,
`active_quarantine`, and `no_warmup`. Keep existing audit events for traceability and document
the rollback reason in the incident or release notes.

## PII compliance — audit log content guarantees

The sensitive audit log path (`record_sensitive_audit_event`) applies
`secret_redaction.redact_pii()` to every payload before insert. Three
layers cover GDPR-class data:

1. **Key-based masking.** Values for any key whose normalized form matches
   an email fragment (`email`, `contact_email`, `owner_email`, `user_email`,
   `actor_email`) collapse to `[REDACTED_EMAIL]`. Phone-shaped keys
   (`phone`, `phone_number`, `contact_phone`, `tg_phone`, `telephone`,
   `mobile`) collapse to `[REDACTED_PHONE]`. Generic secret keys
   (`password`, `token`, `api_hash`, `secret`, ...) keep the legacy `***`
   token — distinct from PII so downstream operators can tell secrets
   apart from contact data.
2. **Pattern-based masking.** Any string value is scanned for free-text
   email/phone substrings. Phone matches require either a leading `+`,
   formatting punctuation (`space`, `.`, `(`, `)`), or three or more
   dash-separated all-digit groups, so opaque IDs and UUID segments are
   left alone. Reason text fields go through the same pipeline.
3. **Recursive nesting.** Dict/list/tuple containers are walked, so
   redaction applies at any depth in the metadata payload.

Implications and limitations:

- **Historical entries are not modified.** Backfilling already-stored
  rows would invalidate the audit trail. Operators reviewing rows older
  than this rollout must treat any plaintext email/phone as legitimate
  evidence of the issue this rollout closes, not as a fresh leak.
- **Best effort, not formal proof.** Phone heuristics are conservative
  to avoid false positives on IDs/UUIDs; pathological formats (e.g. no
  separators and no `+`) may slip through. Add new patterns or key
  fragments here when observed.
- **Out-of-audit-log callsites.** The same `redact_pii()` (or the
  pattern-extended `redact_text()`) should wrap any new structured-log
  emission that may receive caller-supplied free text.
