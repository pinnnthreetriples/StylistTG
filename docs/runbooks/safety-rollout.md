# Safety Pipeline Rollout

> ⚠️ **Workspace Safety Policy temporarily disabled by developer decision (2026-06-04).**
>
> The kill-switch `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED` defaults to
> `True`. While set, `get_workspace_safety_policy()` returns a transient
> neutral policy for every consumer (gate, quarantine, status monitor,
> neuro_commenting, warmup), so workspace-wide behavioral limits, quiet
> hours, and auto-pauses do not apply. The Settings panel
> `apps/dashboard/src/features/settings/SafetyPolicyPanel.tsx` surfaces this
> as a "Временно отключено" banner.
>
> **Why:** the per-workspace behavioral overlay duplicates per-account
> personality work scheduled in the advanced warmup roadmap. Re-enable only
> after per-account behavior (personality seed, channel-state selector,
> circadian windows) ships and absorbs the behavioral fields.
>
> **How to re-enable:** set
> `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED=false` (or flip the default
> in `backend/app/config.py`). No data migration required — persisted policy
> rows are untouched while the switch is on.
>
> **Test posture:** `backend/tests/conftest.py` forces the flag off so the
> underlying policy logic remains under test.

## Pre-flight checklist

- Confirm migrations are applied through `20260525_0054` (account cascade
  policy; latest head as of 2026-05-26). The 0054 sweep is FK-only and
  reflective — see `migration-safety.md#migration-replay-procedure`.
- Confirm `python:3.14-slim-trixie` is the runtime base in both
  `backend/Dockerfile` and `backend/Dockerfile.tdlib` (Python 3.14 +
  Debian Trixie after PR #177).
- Run disposable migration replay (`docker-compose -f
  docker-compose.replay.yml up -d` then
  `python -m scripts.migration_replay --direction roundtrip`). The
  resulting JSON should show every revision upgrade+downgrade clean.
- Confirm the default value for `workspaces.safety_pipeline_v2_enabled` is `false`.
- Confirm safety-policy presets, quarantine, proxy health, and warmup status checks have fresh targeted test coverage.
- Confirm admin access to `PATCH /api/workspaces/{workspace_id}/feature-flags`.
- Confirm monitoring covers safety-gate verdict volume, blocked reasons, queue error rate, and operator overrides.
- Confirm the dashboard observability metrics below are emitting and the
  Grafana panel `Quarantine fraction` is no longer "No data" (fix landed
  in PR #178 — uses `account_total`, not the old `total_accounts`).
- Confirm rollback owners and communication channels are assigned before enabling canaries.
- Confirm `safety_gate_redis_fail_open` is `false` in production
  settings. The Redis fail-closed behavior (PR #175) is the canary
  safety net; flipping the flag during the canary window invalidates the
  rollout signal.

## Canary observability — required panels and thresholds

The metrics below were added or fixed in Tasks 43-53 and form the
canary go/no-go signal. The runbook
[`safety-alerts.md`](safety-alerts.md) holds the Alertmanager
expressions; the values below are the **canary-specific** stop-the-
rollout thresholds, tighter than the prod-wide alerts.

| Metric | Source PR | Watch for | Stop-rollout threshold |
| --- | --- | --- | --- |
| `safety_gate_reserve_outcomes_total{outcome}` | #175 | `REDIS_UNAVAILABLE` spike | any non-zero rate over 5 min |
| `safety_gate_redis_errors_total{operation}` | #175 | sustained Redis outage | rate > 0 for 5 min |
| `safety_gate_redis_fail_open_total{operation}` | #175 | unintended fail-open override | any non-zero increment |
| `account_total{workspace_id}` | #178 | dashboard rendering correct | panel must not be "No data" |
| `weak_ggr_accounts_total{workspace_id}` | #178 | population, not histogram | hour-over-hour delta > 5 |
| `weak_ggr_transitions_total{from,to}` | #178 | medium→weak slide | > 3 medium→weak/h |
| `db_pool_saturation` | #180 | DB pool starvation | sustained > 0.8 for 5 min |
| `redis_pool_saturation` | #180 | Redis pool starvation | sustained > 0.8 for 5 min |
| `safety_gate_evaluate_duration_seconds` | (Task 27) | cold/cache hit p95 | p95 > 200ms cold, > 50ms hit |
| `attempt_send_duration_seconds` | (Task 30) | per-strategy p95 | p95 > 30s |

If any threshold trips during Stage 1, treat as a regression: rollback
per "Rollback procedure" below, file an issue with the metric snapshot,
and do not expand to Stage 2 until the regression has a fix and a
follow-up canary run.

## Stage 1 canary 48h

Enable `safety_pipeline_v2_enabled` for a small named canary workspace set for 48 hours.
Watch for unexpected increases in `blocked` verdicts, stale warmup state, false-positive proxy failures,
and account lifecycle support tickets. Do not expand while unresolved regressions are open.

Additional canary-only watchpoints from Tasks 43-53:

- `comment_send_unexpected_error` events (PR #171). Should be zero
  during the canary. Any occurrence is a real sender bug, not noise.
- `account.deleted` sensitive-audit events (PR #174). If the workspace
  exercises hard-delete during the canary, confirm cascade row counts in
  the audit metadata match `_CASCADE_MODELS` in
  `app/services/account_lifecycle.py`.
- `safety_gate_redis_errors_total{operation="reserve"}` rate (PR #175).
  Should be zero. If non-zero and `safety_gate_redis_fail_open=false`
  (the default), sends are correctly fail-closed — investigate Redis
  health, do not flip the flag.

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

### Migration rollback

Migration `20260525_0054` (account cascade policy, PR #174) is
reflective — it uses `inspect()` to find the existing FK names rather
than guessing — so the downgrade path is safe to run on any
Postgres instance that has the upgrade applied. Re-apply order:

```powershell
cd backend
python -m alembic downgrade 20260523_0053   # one step back
# or for a full rollback to before any safety-pipeline work:
python -m alembic downgrade 20260520_0033   # before WorkspaceSafetyPolicy
```

The cascade migration is intentionally idempotent in both directions —
re-running upgrade after a partial rollback skips FKs that already match
the desired policy.

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
