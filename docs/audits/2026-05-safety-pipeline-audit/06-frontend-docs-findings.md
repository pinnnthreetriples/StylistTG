# Sub-agent F - Frontend, Docs, Spec Compliance Findings

Scope: GitHub issue #148 / Task 42, Sub-agent F. Dimensions covered: 1 spec compliance, 6 time/timezone discipline, 16 frontend quality, 18 documentation freshness.

Write scope honored: this report only.

## Summary

Findings: P0=0, P1=0, P2=2, P3=2.

Overall frontend/docs verdict for this slice: no P0/P1 blocker found. Do not treat as full GO by itself; other sub-agent dimensions still own backend correctness, security, data, migration, resilience, and synthesis.

Evidence used:

- Spec: `docs/superpowers/plans/2026-05-19-three-module-integration-and-account-safety.md`.
- Merged PR/task evidence: `gh pr list --state merged --search "safety-pipeline" --limit 100` and `gh pr list --state merged --search "merged:>=2026-05-19" --limit 100`.
- Docs: `docs/modules/account-safety-pipeline.md`, `docs/runbooks/safety-rollout.md`, `docs/runbooks/safety-alerts.md`, `docs/runbooks/backfill-safety-pipeline.md`, `docs/runbooks/safety-pipeline-preflight-checklist.md`, `README.md`.
- Frontend/API: dashboard safety UI, `packages/api-client/openapi.json`, `packages/api-client/src/generated/schema.d.ts`, `packages/api-client/src/client.ts`.

Commands/checks run:

```powershell
rtk npm run typecheck --workspace=@stylisttg/dashboard
rtk npm run test --workspace=@stylisttg/dashboard -- SafetyGateBanner QuarantineStateBanner SafetyPolicyPanel DisasterModeBanner GGRBadge ProfileCompletenessBar BoughtAccountOnboardingWizard AccountRiskTab
rtk rg -n "datetime\.now\(\)|datetime\.utcnow\(" backend/app backend/tests apps/dashboard/src packages/api-client/src
rtk rg -n "\bany\b|as any|: any|<any>" apps/dashboard/src/features/settings apps/dashboard/src/features/home apps/dashboard/src/features/accounts apps/dashboard/src/modules/shared apps/dashboard/src/modules/neuro-commenting apps/dashboard/src/modules/warmup packages/api-client/src/client.ts
rtk rg -n "console\.(log|debug|warn|error)" apps/dashboard/src packages/api-client/src
rtk rg -n "safety-policy|safety-gate|quarantine|terminal-status|disaster-state|ggr" docs README.md packages/api-client/openapi.json packages/api-client/src/client.ts apps/dashboard/src
```

Frontend targeted verification passed: `tsc --noEmit`; 8 dashboard test files passed, 17 tests passed.

## Findings

### F-006-001: Manual quarantine release UI cannot create the 24h safety-gate override required by Task 32

**Severity**: P2  
**Dimension**: 1 spec compliance, 16 frontend quality  
**Affected**: `apps/dashboard/src/modules/shared/QuarantineStateBanner.tsx:66`; Task 32.2; PR #108/#104 surface  
**Found by**: spec cross-check + targeted `rg`

**Description**: Task 32.2 requires the release modal to include `Reason for early release` plus checkbox `Override safety gate`. Backend contract and route support `override_gate_block`, but the frontend hardcodes `override_gate_block: false` and renders no checkbox. Operators therefore cannot trigger the intended 24h override path from dashboard UI.

**Reproduction**:

```powershell
rtk rg -n "Task 32|override_gate_block|checkbox|Release early" docs/superpowers/plans/2026-05-19-three-module-integration-and-account-safety.md apps/dashboard/src/modules/shared/QuarantineStateBanner.tsx backend/app/contracts/quarantine.py backend/app/api/account_quarantine_routes.py
# Expected: UI exposes checkbox and sends checked value.
# Actual: QuarantineStateBanner sends { override_gate_block: false } unconditionally.
```

**Impact**: Admin release still works, but the documented emergency override flow is incomplete. In production incidents, operators may release quarantine and still see gate blocks without an obvious dashboard control to apply the temporary override.

**Suggested fix**: Add a checkbox state to `QuarantineStateBanner`, label it `Override safety gate`, send its value as `override_gate_block`, and extend `QuarantineStateBanner.test.tsx` for the modal payload.

**Effort estimate**: S

### F-006-002: Grafana quarantine-fraction panel uses a metric name that does not exist

**Severity**: P2  
**Dimension**: 18 documentation freshness  
**Affected**: `docs/grafana/safety-pipeline.json:198`; Task 30/39 observability docs  
**Found by**: docs/code metric cross-check

**Description**: `safety_metrics.py` emits `account_total`, and `docs/runbooks/safety-alerts.md` uses `account_total`. The Grafana dashboard JSON instead divides by `total_accounts`, so the quarantine-fraction panel will not match the emitted metric.

**Reproduction**:

```powershell
rtk rg -n "account_total|total_accounts" backend/app/observability/safety_metrics.py docs/runbooks/safety-alerts.md docs/grafana/safety-pipeline.json
# Expected: one denominator metric name across emitted metrics, alerts, and dashboard.
# Actual: backend/runbook use account_total; Grafana panel uses total_accounts.
```

**Impact**: Operators may see an empty or incorrect quarantine-fraction panel during rollout. This weakens the Task 30/39 observability story and can hide quarantine spikes.

**Suggested fix**: Change the Grafana expression denominator from `total_accounts{...}` to `account_total{...}` and re-validate dashboard JSON.

**Effort estimate**: S

### F-006-003: Safety-policy API-client wrappers bypass generated OpenAPI methods despite exported paths and schemas

**Severity**: P3  
**Dimension**: 16 frontend quality, 18 documentation freshness  
**Affected**: `packages/api-client/src/client.ts:1242`; `packages/api-client/src/generated/schema.d.ts:2201`; `packages/api-client/openapi.json:11339`  
**Found by**: OpenAPI/api-client cross-check

**Description**: OpenAPI export and generated schema include `/api/safety-policy`, but `fetchWorkspaceSafetyPolicy` and `updateWorkspaceSafetyPolicy` call raw `client.request` instead of `client.openapi.GET/PATCH`. The types are still schema-derived, but path/body drift is less likely to be caught by TypeScript.

**Reproduction**:

```powershell
rtk rg -n "/api/safety-policy|fetchWorkspaceSafetyPolicy|updateWorkspaceSafetyPolicy" packages/api-client/openapi.json packages/api-client/src/generated/schema.d.ts packages/api-client/src/client.ts
# Expected: wrappers use generated client.openapi methods for exported endpoints.
# Actual: safety-policy wrappers use client.request('/api/safety-policy').
```

**Impact**: Low immediate runtime risk, but API/client drift can slip through during later safety-policy contract changes.

**Suggested fix**: Switch both wrappers to `unwrap(client.openapi.GET('/api/safety-policy'), ...)` and `unwrap(client.openapi.PATCH('/api/safety-policy', { body: update }), ...)`.

**Effort estimate**: S

### F-006-004: Safety code is UTC-aware, but some pipeline paths bypass the shared `utc_now()` helper

**Severity**: P3  
**Dimension**: 6 time/timezone discipline  
**Affected**: `backend/app/services/ggr_calculator.py:71`; `backend/app/services/account_safety_gate.py:606`; related neuro-commenting/warmup paths found by search  
**Found by**: timezone discipline `rg`

**Description**: No naive `datetime.now()` or `datetime.utcnow()` calls were found in the scoped search. However, multiple safety-pipeline paths still call `datetime.now(UTC)` directly instead of the project helper `utc_now()`, even though issue #148 explicitly asks the pipeline to use `utc_now()` consistently.

**Reproduction**:

```powershell
rtk rg -n "datetime\.now\(UTC\)|now or datetime\.now\(UTC\)" backend/app/services/account_safety_gate.py backend/app/services/ggr_calculator.py backend/app/services/neuro_commenting backend/app/modules/warmup
# Expected: safety pipeline uses utc_now() consistently.
# Actual: GGR age scoring, gate age hours, and several warmup/neuro-commenting helpers use datetime.now(UTC) directly.
```

**Impact**: Current calls are timezone-aware, so this is not a production blocker. The risk is inconsistent clock injection/test discipline around boundary windows such as 24h quarantine, 6h GGR recalculation, and account-age gates.

**Suggested fix**: Convert direct safety-pipeline `datetime.now(UTC)` callsites to `utc_now()` or pass an explicit `now` parameter through boundary-sensitive helpers.

**Effort estimate**: S/M

## Explicit No-issue Checks

- **Naive datetime search**: `rtk rg -n "datetime\.now\(\)|datetime\.utcnow\(" backend/app backend/tests apps/dashboard/src packages/api-client/src` returned no matches.
- **Freeze-time coverage spot check**: timestamp-heavy safety tests use `@freeze_time(_FROZEN_NOW)` / `_NOW` in `test_disaster_state.py`, `test_cross_module_load_tracker.py`, `test_bought_account_onboarding.py`, `test_account_status_monitor.py`, `test_reconcile_stuck_attempts.py`, `test_retention_worker.py`, `test_admin_notifications.py`, and `integration/test_safety_pipeline_e2e.py`.
- **Frontend typecheck**: `rtk npm run typecheck --workspace=@stylisttg/dashboard` passed.
- **Targeted frontend tests**: `rtk npm run test --workspace=@stylisttg/dashboard -- SafetyGateBanner QuarantineStateBanner SafetyPolicyPanel DisasterModeBanner GGRBadge ProfileCompletenessBar BoughtAccountOnboardingWizard AccountRiskTab` passed: 8 files, 17 tests.
- **Safety UI `any`/console scan**: scoped safety/frontend surfaces had no `any` hits and no `console.log/debug/warn/error` hits.
- **Loading/error states**: `SafetyGateBanner`, `ProfileCompletenessBar`, `SafetyPolicyPanel`, and neuro-commenting safety sections expose loading/error branches. `DisasterModeBanner` intentionally renders nothing unless disaster state is true.
- **A11y minimum spot check**: account selection checkboxes have `aria-label`; disaster banner has `aria-label`; profile completeness uses `role="progressbar"` with `aria-valuenow`; detailed account diagnostics use `aria-label`.
- **UI primitive usage**: safety dashboard surfaces use `@stylisttg/ui` primitives (`Button`, `Badge`, `SectionCard`, `Select`, `StatusCard`, `StatusPill`, `RiskBadge`) where equivalents exist.
- **OpenAPI presence**: exported OpenAPI/generated schema include `/api/accounts/{account_id}/safety-gate`, `/api/dashboard/disaster-state`, `/api/safety-policy`, and schemas for `SafetyGateVerdict`, `DisasterState`, `WorkspaceSafetyPolicyRead`, and `WorkspaceSafetyPolicyUpdate`.
- **Docs presence**: `README.md` links `docs/modules/account-safety-pipeline.md`; required Task 39/40 docs exist: `account-safety-pipeline.md`, `safety-rollout.md`, `safety-alerts.md`, `backfill-safety-pipeline.md`, and `safety-pipeline-preflight-checklist.md`.

## Audit Limits / Follow-up Needed

- I did not run full dashboard coverage or ESLint because the checkpoint asked to prioritize writing this file. Targeted typecheck and tests passed.
- I did not run live browser/a11y tooling; no dependency installs were performed.
- I did not perform a full 41-task line-by-line implementation audit. This file records Sub-agent F evidence for assigned dimensions and flags spec/doc/frontend issues found in that pass.
