# Safety Pipeline Production Pre-Flight Checklist

Use this checklist before enabling `safety_pipeline_v2_enabled` for 100% of
production workspaces. It is an operator gate, not an automation script.

Do not run migrations, backfills, production feature-flag changes, or alert
deployments from this PR. Operators run the commands below in staging,
prod-clone, or production only after the normal release approval process.
Do not read `.env*`, logs, `backend/tdlib/`, runtime artifacts, or secrets while
preparing this checklist.

## Required Inputs

- Production or prod-clone database access with read/write rights appropriate
  for the named step.
- Admin API credentials for `PATCH /api/workspaces/{workspace_id}/feature-flags`.
- Redis access for the production safety-gate cache namespace.
- Grafana, Alertmanager, Sentry, and log aggregation access.
- Read-only health access to `/health`, `/ready`, and `/metrics`.
- Task 38 E2E issue: [#141](https://github.com/pinnnthreetriples/StylistTG/issues/141).
- Task 39 documentation issue: [#142](https://github.com/pinnnthreetriples/StylistTG/issues/142).
- Architecture document:
  [account-safety-pipeline.md](../modules/account-safety-pipeline.md).

## Traceability

| Phase item | Source | Current artifact |
| --- | --- | --- |
| Task 20 feature flag | PR [#106](https://github.com/pinnnthreetriples/StylistTG/pull/106) | `PATCH /api/workspaces/{workspace_id}/feature-flags`, [safety-rollout.md](safety-rollout.md) |
| Task 27 gate performance budget | PR [#127](https://github.com/pinnnthreetriples/StylistTG/pull/127) | [perf-benchmarks.md](perf-benchmarks.md) |
| Task 28 backfill | Issue [#135](https://github.com/pinnnthreetriples/StylistTG/issues/135), PR [#138](https://github.com/pinnnthreetriples/StylistTG/pull/138) | [backfill-safety-pipeline.md](backfill-safety-pipeline.md) |
| Task 29 migration safety | PR [#112](https://github.com/pinnnthreetriples/StylistTG/pull/112) | `backend/tools/migration_lint.py` |
| Task 30 observability | PR [#124](https://github.com/pinnnthreetriples/StylistTG/pull/124) | [safety-alerts.md](safety-alerts.md), `../grafana/safety-pipeline.json` |
| Task 31 admin alerts | PR [#125](https://github.com/pinnnthreetriples/StylistTG/pull/125) | workspace notification settings and alert escalation path |
| Task 38 E2E scenarios | Issue [#141](https://github.com/pinnnthreetriples/StylistTG/issues/141), PR [#147](https://github.com/pinnnthreetriples/StylistTG/pull/147) | `backend/tests/integration/test_safety_pipeline_e2e.py` |
| Task 39 operator docs | Issue [#142](https://github.com/pinnnthreetriples/StylistTG/issues/142), PR [#146](https://github.com/pinnnthreetriples/StylistTG/pull/146) | [account-safety-pipeline.md](../modules/account-safety-pipeline.md) |
| Task 43 sender failure cleanup (F-001, F-002) | PR [#171](https://github.com/pinnnthreetriples/StylistTG/pull/171) | `backend/app/services/neuro_commenting/sender_service.py` finalization paths |
| Task 44 Redis-degraded mode (F-301, F-305, B F-004) | PR [#175](https://github.com/pinnnthreetriples/StylistTG/pull/175) | `safety_gate_reserve.py` (fail-closed + ZSET), [safety-alerts.md](safety-alerts.md#safetygateredisdegraded) |
| Task 45 account cascade (F-E001) | PR [#174](https://github.com/pinnnthreetriples/StylistTG/pull/174) | migration `20260525_0054`, [account-deletion-policy.md](account-deletion-policy.md), `hard_delete_account` |
| Task 46 migration replay (F-E002/3/6) | PR [#176](https://github.com/pinnnthreetriples/StylistTG/pull/176) | `docker-compose.replay.yml`, `scripts/migration_replay.py`, [migration-safety.md](migration-safety.md#migration-replay-procedure) |
| Task 47 PII redaction (B F-001) | PR [#173](https://github.com/pinnnthreetriples/StylistTG/pull/173) | `secret_redaction.redact_pii()` + UUID-context detection, [safety-rollout.md PII compliance](safety-rollout.md#pii-compliance--audit-log-content-guarantees) |
| Task 48 dev env + tooling (F-041) | PR [#170](https://github.com/pinnnthreetriples/StylistTG/pull/170) | `backend/pyproject.toml [dev]` extras, [dev-environment-setup.md](dev-environment-setup.md) |
| Task 49 observability fixes (F-302, F-304) | PR [#178](https://github.com/pinnnthreetriples/StylistTG/pull/178) | `account_total`, `weak_ggr_accounts_total`, `weak_ggr_transitions_total` metrics + dashboard validity test |
| Task 50 safety state hardening (F-005/6, B F-002/3) | PR [#179](https://github.com/pinnnthreetriples/StylistTG/pull/179) | quarantine idempotency, monitor batching, `account_safety_override.workspace_id` |
| Task 51 ops hardening (F-E004, F-306, B F-005, F-E005, F-004) | PR [#180](https://github.com/pinnnthreetriples/StylistTG/pull/180) | DB/Redis timeouts, deterministic backfill seed, reconcile workspace scope |
| Task 52 E2E + behavior decision (F-042, F-008) | PR [#182](https://github.com/pinnnthreetriples/StylistTG/pull/182) | workflow-driven E2E asserts, behavior emulator scope doc |
| Task 53 UI override + utc_now + client (F-006-001/3/4, F-007) | PR [#181](https://github.com/pinnnthreetriples/StylistTG/pull/181) | `QuarantineStateBanner` override checkbox, `utc_now()` sweep, generated OpenAPI client |
| Python 3.14 upgrade | PR [#177](https://github.com/pinnnthreetriples/StylistTG/pull/177) | Dockerfiles, `pyproject.toml`, CI workflows, branch protection check name |

## 1. Pre-Deploy Verification

Run these checks one day before go-live. Record the command output, owner, and
timestamp in the release notes or rollout ticket.

- [ ] **Migrations applied on prod-clone** (Task 29, PR
  [#112](https://github.com/pinnnthreetriples/StylistTG/pull/112)).

  Run against a production clone, not production:

  ```powershell
  cd backend
  Measure-Command { python -m alembic upgrade head }
  python -m tools.migration_lint --base origin/main
  ```

  Expected result: migrations `20260520_0034` through `20260525_0054` apply
  without blocking any statement for more than 5 seconds, and migration lint exits
  successfully. The `20260525_0054_account_safety_cascade` step (Task 45) is
  FK-reflective — on a populated DB it issues one `ALTER TABLE … DROP CONSTRAINT
  … ADD CONSTRAINT … ON DELETE …` per safety-pipeline FK and finishes in tens
  of milliseconds. If timing is unclear, repeat with database-side lock
  monitoring:

  ```sql
  select pid, wait_event_type, wait_event, query
  from pg_stat_activity
  where wait_event_type = 'Lock';
  ```

- [ ] **Backfill executed in staging** (Task 28, issue
  [#135](https://github.com/pinnnthreetriples/StylistTG/issues/135), PR
  [#138](https://github.com/pinnnthreetriples/StylistTG/pull/138)).

  Follow [backfill-safety-pipeline.md](backfill-safety-pipeline.md). Minimum
  staging commands:

  ```powershell
  cd backend
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --dry-run --batch-size 1000
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --batch-size 1000
  python -m scripts.backfill_safety_pipeline --workspace-id <staging-workspace-uuid> --dry-run --batch-size 1000
  ```

  Expected result: final dry run reports zero missing GGR scores, behavior
  profiles, origin markers, and grace-period rows. Confirm with the verification
  queries in [backfill-safety-pipeline.md](backfill-safety-pipeline.md#verification-queries).

- [ ] **Feature flag verified for canary workspace** (Task 20, PR
  [#106](https://github.com/pinnnthreetriples/StylistTG/pull/106)).

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

  Expected result: workspace response has `"safety_pipeline_v2_enabled": true`.
  The safety-gate response uses full v2 reasons when data requires them, not only
  the legacy shim reasons `proxy_unhealthy`, `active_quarantine`, and `no_warmup`.

- [ ] **Grafana dashboard deployed** (Task 30, PR
  [#124](https://github.com/pinnnthreetriples/StylistTG/pull/124)).

  Import `../grafana/safety-pipeline.json` into Grafana using the production
  Prometheus data source. Then run:

  ```powershell
  curl.exe -sS -H "Authorization: Bearer <grafana-token>" `
    "https://<grafana-host>/api/search?query=Safety%20Pipeline"
  ```

  Expected result: the Safety Pipeline dashboard is present, all 6 safety panels
  load for the canary workspace, and no panel shows `No data` after selecting the
  active Prometheus data source.

- [ ] **Alertmanager rules deployed** (Tasks 30 and 31, PRs
  [#124](https://github.com/pinnnthreetriples/StylistTG/pull/124) and
  [#125](https://github.com/pinnnthreetriples/StylistTG/pull/125)).

  Follow [safety-alerts.md](safety-alerts.md). Confirm at least these rules are
  active: `QuarantineEpidemic`, `WeakGgrAccountsGrowth`, `GateBlockBurst`,
  `SendDurationSlow`.

  ```powershell
  amtool config routes test --config.file=<alertmanager.yml> `
    --tree --verify.receivers=safety-pipeline-slack severity=warning service=safety-pipeline

  amtool alert add GateBlockBurst `
    severity=critical service=safety-pipeline workspace_id=<canary-workspace-uuid>
  ```

  Expected result: warning alerts route to the safety-pipeline Slack receiver,
  critical alerts route to PagerDuty or the configured phone escalation, and the
  test alert is visible in the expected destination.

- [ ] **On-call runbooks reviewed** (Task 39, issue
  [#142](https://github.com/pinnnthreetriples/StylistTG/issues/142), PR
  [#146](https://github.com/pinnnthreetriples/StylistTG/pull/146)).

  Confirm on-call reviewers have signed off on:

  ```powershell
  Test-Path docs/runbooks/safety-rollout.md
  Test-Path docs/runbooks/safety-alerts.md
  Test-Path docs/runbooks/backfill-safety-pipeline.md
  Test-Path docs/modules/account-safety-pipeline.md
  ```

  Expected result: all paths exist. Sign-off is recorded as PR review approval,
  Notion acknowledgement, or Confluence acknowledgement from every named on-call
  engineer.

- [ ] **Load test passed** (Task 27, PR
  [#127](https://github.com/pinnnthreetriples/StylistTG/pull/127)).

  Confirm the last 7 nightly benchmark runs meet [perf-benchmarks.md](perf-benchmarks.md).
  For an ad-hoc staging run:

  ```powershell
  cd backend
  uv run --extra test pytest tests/benchmarks/ `
    --benchmark-enable `
    --benchmark-only `
    --benchmark-storage=file://./benchmark_storage `
    --benchmark-compare=tests/benchmarks/baselines/safety_gate_baseline.json `
    --benchmark-compare-fail=mean:20%
  ```

  Optional HTTP load check against staging:

  ```powershell
  @'
  import http from "k6/http";
  import { check } from "k6";

  export const options = {
    scenarios: {
      safety_gate: {
        executor: "constant-arrival-rate",
        rate: 500,
        timeUnit: "1s",
        duration: "5m",
        preAllocatedVUs: 100,
        maxVUs: 500,
      },
    },
    thresholds: {
      http_req_failed: ["rate<0.01"],
      http_req_duration: ["p(95)<400"],
    },
  };

  export default function () {
    const url = `${__ENV.API_BASE_URL}/api/accounts/${__ENV.ACCOUNT_ID}/safety-gate?intent=commenting`;
    const res = http.get(url, {
      headers: { Authorization: `Bearer ${__ENV.ADMIN_JWT}` },
    });
    check(res, { "status is 200": (response) => response.status === 200 });
  }
  '@ | Set-Content -LiteralPath "$env:TEMP\safety_gate_500qps.js"

  k6 run "$env:TEMP\safety_gate_500qps.js" `
    -e API_BASE_URL=https://<staging-api> `
    -e ACCOUNT_ID=<staging-account-uuid> `
    -e ADMIN_JWT=<admin-jwt>
  ```

  Expected result: `gate.evaluate` p95 is under 50 ms for cache hits and under
  200 ms for cold calls; `gate.reserve` p95 is under 5 ms; 500 qps for 5 minutes
  does not fail and p95 does not grow by more than 2x.

- [ ] **E2E scenarios green** (Task 38, issue
  [#141](https://github.com/pinnnthreetriples/StylistTG/issues/141), PR
  [#147](https://github.com/pinnnthreetriples/StylistTG/pull/147)).

  Verify the latest CI run or run locally:

  ```powershell
  cd backend
  python -m pytest tests/integration/test_safety_pipeline_e2e.py -v
  ```

  Expected result: 6 of 6 production-critical scenarios pass with fake TDLib
  only, no live Telegram calls, and `AccountSafetyGate.evaluate` coverage
  recorded in the test output or PR notes.

## 2. Rollout Day Actions

- [ ] **Send operator communication.**

  Post to `<operator-channel>` before changing any production flag:

  ```text
  Safety pipeline v2 rollout starts at <time>.
  Rollout plan: docs/runbooks/safety-rollout.md
  Alerts: docs/runbooks/safety-alerts.md
  Rollback owner: <name>
  Current stage: first real workspace outside canary, 24h hold.
  ```

- [ ] **Enable the first real workspace and hold for 24 hours.**

  ```powershell
  $ApiBaseUrl = "https://<prod-api>"
  $WorkspaceId = "<first-real-workspace-uuid>"
  $Token = "<admin-jwt>"

  curl.exe -sS -X PATCH "$ApiBaseUrl/api/workspaces/$WorkspaceId/feature-flags" `
    -H "Authorization: Bearer $Token" `
    -H "Content-Type: application/json" `
    -d '{"safety_pipeline_v2_enabled": true}'
  ```

  Expected result: only the named workspace is enabled. No batch update is run
  during this step.

- [ ] **Open monitoring windows.**

  Keep these views open and filtered to the workspace when possible:

  - Grafana dashboard imported from `../grafana/safety-pipeline.json`.
  - Alertmanager route and firing alerts view.
  - Sentry project for backend exceptions.
  - Log aggregation query for `service=safety-pipeline` and the target workspace.

- [ ] **Run rollout checkpoints at T+1h, T+4h, and T+12h.**

  Check these metrics at each checkpoint:

  ```promql
  quarantine_active{workspace_id="<workspace-id>"}
  sum by (reason) (rate(safety_gate_blocks_total{workspace_id="<workspace-id>"}[5m]))
  histogram_quantile(0.95, sum by (le) (rate(attempt_send_duration_seconds_bucket[5m])))
  histogram_quantile(0.95, sum by (le, cache_hit) (rate(safety_gate_evaluate_duration_seconds_bucket[5m])))
  ```

  Expected result: quarantine ratio remains below 10%, gate block reasons match
  baseline, send p95 remains below 30 seconds, and safety-gate latency remains
  inside the Task 27 budget.

## 3. Rollback Playbook

Prefer per-workspace rollback. Batch rollback is only for a confirmed systemic
regression.

### Per-Workspace Rollback

```powershell
$ApiBaseUrl = "https://<prod-api>"
$WorkspaceId = "<workspace-uuid>"
$Token = "<admin-jwt>"

curl.exe -sS -X PATCH "$ApiBaseUrl/api/workspaces/$WorkspaceId/feature-flags" `
  -H "Authorization: Bearer $Token" `
  -H "Content-Type: application/json" `
  -d '{"safety_pipeline_v2_enabled": false}'
```

### Batch Rollback

Use one transaction and record the affected workspace ids in the incident notes:

```sql
begin;

update workspace
set safety_pipeline_v2_enabled = false,
    updated_at = now()
where id = any(string_to_array(:'workspace_ids_csv', ',')::uuid[])
  and safety_pipeline_v2_enabled is true
returning id, slug, safety_pipeline_v2_enabled;

commit;
```

Run it with a comma-separated list of affected workspace ids:

```powershell
$RollbackSql = @'
begin;

update workspace
set safety_pipeline_v2_enabled = false,
    updated_at = now()
where id = any(string_to_array(:'workspace_ids_csv', ',')::uuid[])
  and safety_pipeline_v2_enabled is true
returning id, slug, safety_pipeline_v2_enabled;

commit;
'@

$RollbackSql | psql "$env:DATABASE_DIRECT_URL" `
  -v workspace_ids_csv="$env:WORKSPACE_IDS_CSV"
```

Clear safety-gate cache keys for affected accounts after the DB update:

```powershell
$AccountIds = psql "$env:DATABASE_DIRECT_URL" -At `
  -v workspace_id="$env:WORKSPACE_ID" `
  -c "select id from account where workspace_id = :'workspace_id';"

foreach ($AccountId in $AccountIds) {
  foreach ($Intent in @("editing", "warmup", "commenting")) {
    redis-cli -u "$env:REDIS_URL" --scan --pattern "safety:gate:${AccountId}:${Intent}:*" `
      | ForEach-Object { redis-cli -u "$env:REDIS_URL" DEL $_ }

    redis-cli -u "$env:REDIS_URL" DEL `
      "safety:gate:stale:${AccountId}:${Intent}" `
      "gate:cold:${AccountId}:${Intent}"
  }

  redis-cli -u "$env:REDIS_URL" DEL "safety:gate:concurrent:${AccountId}:commenting"

  redis-cli -u "$env:REDIS_URL" --scan --pattern "safety:gate:reservation:${AccountId}:*" `
    | ForEach-Object { redis-cli -u "$env:REDIS_URL" DEL $_ }
}
```

If Redis is shared by multiple environments, use the environment-specific Redis
database or key prefix instead of a global scan.

### Rollback Verification

```powershell
$ApiBaseUrl = "https://<prod-api>"
$AccountId = "<affected-account-uuid>"
$Token = "<admin-jwt>"

curl.exe -sS "$ApiBaseUrl/api/accounts/$AccountId/safety-gate?intent=commenting" `
  -H "Authorization: Bearer $Token"
```

Expected result: new evaluations use only legacy shim reasons:
`proxy_unhealthy`, `active_quarantine`, and `no_warmup`. Alert rates for
`safety_gate_blocks_total`, `quarantine_active`, and
`attempt_send_duration_seconds` return to baseline or stop worsening within the
incident window.

## 4. Post-Rollout Retrospective

Create a retrospective note after the 24h hold or immediately after rollback.

- [ ] What worked well?
- [ ] What surprised operators or users?
- [ ] Which alerts were too noisy or too quiet?
- [ ] Which runbook step was unclear or missing?
- [ ] Which follow-up issues should be opened?
- [ ] Were Task 38 and Task 39 merged before rollout? If not, what extra review
  compensated for the dependency gap?
- [ ] Update [safety-rollout.md](safety-rollout.md), [safety-alerts.md](safety-alerts.md),
  or [backfill-safety-pipeline.md](backfill-safety-pipeline.md) if the rollout
  found a durable documentation gap.

## PR Note Template

Use this in the PR that adds or updates this checklist:

```markdown
Closes #143

This PR creates the production pre-flight checklist only. It does not execute
the checklist, enable production flags, deploy alerts, run backfills, or run
production migrations. Real execution remains an operator task after merge.

Dependencies:
- Task 38: #141 / #147, merged before this checklist.
- Task 39: #142 / #146, merged before this checklist.

Final task of Phase 3. Closes 40/40 plan.
```
