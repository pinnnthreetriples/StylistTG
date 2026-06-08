# Safety Pipeline Production Pre-Flight Checklist

Use this checklist before enabling `safety_pipeline_v2_enabled` for 100% of production workspaces. It is an operator gate, not an automation script.

Current status: Workspace Safety Policy is temporarily neutralized by `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED=True`. Operators must resolve or explicitly account for that status before any production rollout. Agents must read `.mex/status/current.md` before safety rollout work.

Do not run migrations, backfills, production feature-flag changes, or alert deployments from an agent session. Operators run the commands below in staging, prod-clone, or production only after normal release approval. Do not read `.env*`, logs, `backend/tdlib/`, runtime artifacts, or secrets while preparing this checklist.

## Required Inputs

- Production or prod-clone database access with read/write rights appropriate for the named step.
- Admin API credentials for `PATCH /api/workspaces/{workspace_id}/feature-flags`.
- Redis access for the production safety-gate cache namespace.
- Grafana, Alertmanager, Sentry, and log aggregation access.
- Read-only health access to `/health`, `/ready`, and `/metrics`.
- Architecture document: `docs/modules/account-safety-pipeline.md`.
- Current status memory: `.mex/status/current.md`.

## Traceability

Detailed PR/issue traceability for the original rollout tasks remains in GitHub. This checklist only records the current operator gates and source artifacts.

| Phase item | Current artifact |
| --- | --- |
| Feature flag | `PATCH /api/workspaces/{workspace_id}/feature-flags`, `docs/runbooks/safety-rollout.md` |
| Gate performance budget | `docs/runbooks/perf-benchmarks.md` |
| Backfill | `docs/runbooks/backfill-safety-pipeline.md` |
| Migration safety | `backend/tools/migration_lint.py`, `docs/runbooks/migration-safety.md` |
| Observability | `docs/runbooks/safety-alerts.md`, `docs/grafana/safety-pipeline.json` |
| E2E scenarios | `backend/tests/integration/test_safety_pipeline_e2e.py` |
| Architecture | `docs/modules/account-safety-pipeline.md` |
| Required status override | `.mex/status/current.md` |

## 1. Pre-Deploy Verification

Record command output, owner, and timestamp in the release notes or rollout ticket.

- [ ] **Current status reviewed**

  Confirm `.mex/status/current.md` has been reviewed and the team has decided whether Workspace Safety Policy remains neutralized or is re-enabled for the rollout.

- [ ] **Migrations applied on prod-clone**

  Run against a production clone, not production:

  ```powershell
  cd backend
  Measure-Command { python -m alembic upgrade head }
  python -m tools.migration_lint --base origin/main
  python -m alembic heads
  python -m alembic current
  ```

  Expected result: current Alembic `head` applies cleanly. As of the 2026-05-26 safety state hardening work, safety migration expectations include `20260526_0056` and merge revision `20260526_0057`; do not stop verification at `20260525_0054`.

- [ ] **Backfill executed in staging**

  Follow `docs/runbooks/backfill-safety-pipeline.md`. Minimum staging commands:

  ```powershell
  cd backend
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --dry-run --batch-size 1000
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --batch-size 1000
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --dry-run --batch-size 1000
  ```

  Expected result: final dry run reports zero missing safety state required by the rollout.

- [ ] **Feature flag verified for canary workspace**

  Confirm the API and metrics endpoint are healthy before toggling:

  ```powershell
  $ApiBaseUrl = "https://<staging-or-prod-api>"

  curl.exe -fsS "$ApiBaseUrl/health"
  curl.exe -fsS "$ApiBaseUrl/ready"
  curl.exe -fsS -H "X-Internal-Scrape: true" "$ApiBaseUrl/metrics" `
    | Select-String "safety_gate_blocks_total|safety_gate_evaluate_duration_seconds"
  ```

  Enable only the named canary workspace:

  ```powershell
  $WorkspaceId = "<canary-workspace-uuid>"
  $AccountId = "<canary-account-uuid>"
  $Token = "<admin-jwt>"

  curl.exe -sS -X PATCH "$ApiBaseUrl/api/workspaces/$WorkspaceId/feature-flags" `
    -H "Authorization: Bearer $Token" `
    -H "Content-Type: application/json" `
    -d '{"safety_pipeline_v2_enabled": true}'

  curl.exe -sS "$ApiBaseUrl/api/accounts/$AccountId/safety-gate?intent=commenting" `
    -H "Authorization: Bearer $Token"
  ```

  Expected result: workspace response has `"safety_pipeline_v2_enabled": true`. If `WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED=True`, document that policy-dependent behavior is still neutralized.

- [ ] **Grafana dashboard deployed**

  Import `docs/grafana/safety-pipeline.json` into Grafana using the production Prometheus data source.

- [ ] **Alertmanager rules deployed**

  Follow `docs/runbooks/safety-alerts.md`. Confirm at least these rules are active: `QuarantineEpidemic`, `WeakGgrAccountsGrowth`, `GateBlockBurst`, `SendDurationSlow`.

- [ ] **On-call runbooks reviewed**

  Confirm reviewers have signed off on:

  ```powershell
  Test-Path docs/runbooks/safety-rollout.md
  Test-Path docs/runbooks/safety-alerts.md
  Test-Path docs/runbooks/backfill-safety-pipeline.md
  Test-Path docs/modules/account-safety-pipeline.md
  Test-Path .mex/status/current.md
  ```

- [ ] **Load test passed**

  Confirm the last relevant benchmark run meets `docs/runbooks/perf-benchmarks.md`, or run a staging benchmark approved by the operator.

## 2. Rollout Stages

Follow `docs/runbooks/safety-rollout.md`:

1. Stage 1 canary for 48h.
2. Stage 2 10% by id hash for 5 days.
3. Stage 3 50% for 3 days.
4. Stage 4 100% only after Stage 3 is stable.

## 3. Rollback

Rollback starts by setting `safety_pipeline_v2_enabled=false` for affected workspaces through the admin feature-flag API. Migration rollback must be explicitly approved and performed by operators after checking `python -m alembic current` and `python -m alembic heads`.

Do not run production downgrades, backfills, or destructive cleanup from an agent session.
