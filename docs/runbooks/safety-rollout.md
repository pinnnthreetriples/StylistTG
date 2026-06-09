# Safety Pipeline Rollout

> Current status: Workspace Safety Policy is temporarily disabled by developer decision (2026-06-04).
>
> The kill-switch `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED` defaults to `True`. While set, `get_workspace_safety_policy()` returns a neutral transient policy for every consumer, including gate, quarantine, status monitor, neuro-commenting, and warmup. Workspace-wide behavioral limits, quiet hours, and auto-pauses do not apply while the switch is on.
>
> Why: the per-workspace behavioral overlay duplicates per-account behavior scheduled in the advanced warmup roadmap. Re-enable only after per-account behavior ships and absorbs the duplicated fields: personality seed, channel-state selector, and circadian windows.
>
> How to re-enable: set `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED=false` or flip the default in `backend/app/config.py`. No data migration is required; persisted policy rows are untouched while the switch is on.
>
> Operator approval required: agents must not flip this flag, edit the default, or enable rollout stages without an explicit operator task requesting that change.
>
> Test posture: `backend/tests/conftest.py` forces the flag off so the underlying policy logic remains under test.

See `.mex/status/current.md` for the current memory entry agents must read before safety, live runtime, warmup, rollout, or deploy work.

## Pre-flight checklist

- Confirm migrations are applied through current Alembic `head`. As of the 2026-05-26 safety state hardening work, this includes `20260526_0056` and merge revision `20260526_0057`.
- Confirm `python:3.14-slim-trixie` is the runtime base in both `backend/Dockerfile` and `backend/Dockerfile.tdlib`.
- Run disposable migration replay (`docker-compose -f docker-compose.replay.yml up -d` then `python -m scripts.migration_replay --direction roundtrip`).
- Confirm the default value for `workspaces.safety_pipeline_v2_enabled` is `false` until an approved rollout stage flips it.
- Confirm safety-policy presets, quarantine, proxy health, and warmup status checks have fresh targeted test coverage.
- Confirm admin access to `PATCH /api/workspaces/{workspace_id}/feature-flags`.
- Confirm monitoring covers safety-gate verdict volume, blocked reasons, queue error rate, Redis failures, and operator overrides.
- Confirm `safety_gate_redis_fail_open` is `false` in production settings. Redis-degraded paths should fail closed during canary.
- Confirm rollback owners and communication channels are assigned before enabling canaries.

## Canary observability

The canary signal uses the metrics and alerts documented in `safety-alerts.md` plus the dashboard JSON under `docs/grafana/`.

Watch at minimum:

| Metric | Watch for | Stop-rollout threshold |
| --- | --- | --- |
| `safety_gate_reserve_outcomes_total{outcome}` | `REDIS_UNAVAILABLE` spike | any non-zero rate over 5 min |
| `safety_gate_redis_errors_total{operation}` | sustained Redis outage | rate > 0 for 5 min |
| `safety_gate_redis_fail_open_total{operation}` | unintended fail-open override | any non-zero increment |
| `account_total{workspace_id}` | dashboard rendering correct | panel must not be `No data` |
| `weak_ggr_accounts_total{workspace_id}` | weak population growth | hour-over-hour delta > 5 |
| `weak_ggr_transitions_total{from,to}` | medium-to-weak slide | > 3 medium-to-weak/h |
| `db_pool_saturation` | DB pool starvation | sustained > 0.8 for 5 min |
| `redis_pool_saturation` | Redis pool starvation | sustained > 0.8 for 5 min |
| `safety_gate_evaluate_duration_seconds` | cold/cache hit p95 | p95 > 200ms cold, > 50ms hit |
| `attempt_send_duration_seconds` | per-strategy p95 | p95 > 30s |

If any threshold trips during Stage 1, rollback and do not expand until the regression is fixed and a follow-up canary run is green.

## Stage 1 canary 48h

Enable `safety_pipeline_v2_enabled` for a small named canary workspace set for 48 hours. Watch for unexpected blocked-verdict growth, stale warmup state, false-positive proxy failures, Redis degraded behavior, and support tickets.

## Stage 2 10% 5 days by id hash

Enable the flag for workspaces whose stable workspace id hash falls into the first 10% bucket. Hold for 5 days and compare blocked reason distribution, action throughput, and audit event volume against the prior 7-day baseline.

## Stage 3 50% 3 days

Expand the id-hash bucket to 50% of workspaces for 3 days. Keep a daily review of false positives, quarantine volume, operator override requests, Redis errors, and DB/Redis pool saturation.

## Stage 4 100%

Enable for all active workspaces after Stage 3 is stable. Keep the feature flag writable until legacy shim removal has its own migration and rollback plan.

## Rollback procedure

Set `safety_pipeline_v2_enabled=false` for affected workspaces through the admin feature-flag API. Verify new safety-gate evaluations return only the legacy shim reasons: `proxy_unhealthy`, `active_quarantine`, and `no_warmup`. Keep existing audit events for traceability and document the rollback reason in the incident or release notes.

### Migration rollback

Use current Alembic revision history rather than hardcoding an old head. The safety state hardening path includes `20260526_0056` and merge revision `20260526_0057`; inspect `python -m alembic heads` and the target deployment revision before rollback.

Example one-step rollback from head should be chosen by operators after confirming the active head:

```powershell
cd backend
python -m alembic current
python -m alembic heads
```

Do not run production downgrades from an agent session. Operators must approve and execute rollback commands.

## PII compliance — audit log content guarantees

The sensitive audit log path (`record_sensitive_audit_event`) applies `secret_redaction.redact_pii()` to every payload before insert.

Coverage:

1. Key-based masking for email, phone, and secret-like keys.
2. Pattern-based masking for free-text email/phone substrings.
3. Recursive redaction through dict/list/tuple containers.

Implications and limitations:

- Historical entries are not modified; backfilling already-stored rows would invalidate the audit trail.
- Best effort, not formal proof. Add new patterns or key fragments when observed.
- Out-of-audit-log structured logging that may receive caller-supplied free text should use the same redaction helpers.
