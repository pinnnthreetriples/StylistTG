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
