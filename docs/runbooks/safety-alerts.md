# Safety Pipeline Alerts

Task 30 observability covers Prometheus metrics, Alertmanager rules, and the Grafana dashboard at `docs/grafana/safety-pipeline.json`.

## Scrape target

- Endpoint: `/metrics`.
- Default access: internal scrape only. Send `X-Internal-Scrape: true` unless `metrics_allow_public=true` is explicitly enabled for the environment.
- Do not expose raw account ids in metric labels. Account-level flood-wait metrics should use the short `account_id_hash` label.

## Metrics

| Metric | Type | Labels | Use |
| --- | --- | --- | --- |
| `safety_gate_blocks_total` | counter | `workspace_id`, `intent`, `reason` | Gate block volume and blocked-reason bursts. |
| `quarantine_active` | gauge | `workspace_id`, `reason` | Active quarantine count by workspace and reason. |
| `account_total` | gauge | `workspace_id` | Account denominator for quarantine fraction. |
| `ggr_score` | histogram | `workspace_id`, `bucket` | GGR distribution; `bucket="weak"` tracks weak-account growth. |
| `flood_wait_total` | counter | `workspace_id`, `account_id_hash` | Flood-wait spikes without raw account ids. |
| `attempt_send_duration_seconds` | histogram | `strategy` | Send attempt latency SLO. |
| `safety_gate_evaluate_duration_seconds` | histogram | `intent`, `cache_hit` | Safety gate evaluation latency and cache behavior. |
| `human_behavior_typing_emit_total` | counter | `outcome` | Human-behavior typing emission health. |
| `cross_module_overload_total` | counter | `workspace_id`, `severity` | Cross-module safety overload events. |

If the exporter exposes `workspace` instead of `workspace_id`, adjust the label names in the rules and dashboard during deployment.

## Severity Ladder

Warning alerts page the safety-pipeline Slack channel and email the owning operator group during business hours. They block further rollout expansion until the metric returns to baseline.

Critical alerts page PagerDuty and phone escalation immediately. They require an incident owner, workspace impact notes, and an explicit decision on feature-flag rollback.

## SLO Mapping

| SLO | Metrics | Alert |
| --- | --- | --- |
| Quarantine ratio stays under 10% per workspace. | `quarantine_active`, `account_total` | `QuarantineEpidemic` |
| Weak GGR population does not grow faster than 5 accounts/hour. | `ggr_score_bucket{bucket="weak"}` | `GgrWeakBucketGrowth` |
| Safety gate false-positive bursts are caught within 10 minutes. | `safety_gate_blocks_total{reason="ggr_too_low"}` | `GateBlockBurst` |
| Comment send p95 latency stays under 30 seconds. | `attempt_send_duration_seconds_bucket` | `SendDurationSlow` |
| Cross-module overload remains visible during rollout. | `cross_module_overload_total` | Dashboard panel, manual incident review |

## Rollback

Rollback is per-workspace unless multiple workspaces show the same regression. Use the workspace feature-flag API to disable safety pipeline v2:

```http
PATCH /api/workspaces/{workspace_id}/feature-flags
Content-Type: application/json

{"safety_pipeline_v2_enabled": false}
```

Keep Prometheus scraping enabled during rollback so recovery and residual risk remain visible.

## Alert Rules

```yaml
groups:
  - name: safety-pipeline
    rules:
      - alert: QuarantineEpidemic
        expr: |
          (
            sum by (workspace_id) (quarantine_active)
            /
            clamp_min(sum by (workspace_id) (total_accounts), 1)
          ) > 0.1
        for: 1h
        labels:
          severity: warning
          service: safety-pipeline
        annotations:
          summary: "More than 10% of workspace accounts are quarantined"
          description: "Workspace {{ $labels.workspace_id }} has quarantine_active / account_total above 0.1 for 1h."
          runbook_url: "docs/runbooks/safety-alerts.md#quarantineepidemic"

      - alert: GgrWeakBucketGrowth
        expr: |
          sum by (workspace_id) (
            increase(ggr_score_bucket{bucket="weak"}[1h])
          ) > 5
        for: 10m
        labels:
          severity: warning
          service: safety-pipeline
        annotations:
          summary: "Weak GGR bucket growing faster than 5 accounts/hour"
          description: "Workspace {{ $labels.workspace_id }} has weak GGR growth above 5 per hour."
          runbook_url: "docs/runbooks/safety-alerts.md#ggrweakbucketgrowth"

      - alert: GateBlockBurst
        expr: |
          sum by (workspace_id) (
            rate(safety_gate_blocks_total{reason="ggr_too_low"}[1m])
          ) * 60 > 50
        for: 5m
        labels:
          severity: critical
          service: safety-pipeline
        annotations:
          summary: "GGR-too-low gate block burst"
          description: "Workspace {{ $labels.workspace_id }} has more than 50 ggr_too_low blocks per minute."
          runbook_url: "docs/runbooks/safety-alerts.md#gateblockburst"

      - alert: SendDurationSlow
        expr: |
          histogram_quantile(
            0.95,
            sum by (le, strategy) (
              rate(attempt_send_duration_seconds_bucket[5m])
            )
          ) > 30
        for: 15m
        labels:
          severity: warning
          service: safety-pipeline
        annotations:
          summary: "Send attempt p95 latency above 30s"
          description: "Strategy {{ $labels.strategy }} has attempt_send_duration_seconds p95 above 30s."
          runbook_url: "docs/runbooks/safety-alerts.md#senddurationslow"
```

## QuarantineEpidemic

Severity: warning.

1. Open the Safety Pipeline Grafana dashboard and filter to the affected `workspace_id`.
2. Confirm the fraction with `quarantine_active / account_total` and compare against the previous 24h baseline.
3. Check gate block reasons. If `active_quarantine`, `proxy_unhealthy`, or `flood_wait_streak` dominates, inspect the matching runtime provider before releasing accounts.
4. Pause rollout expansion for the workspace. If this started during a canary or staged rollout, keep `safety_pipeline_v2_enabled` unchanged for unaffected workspaces.
5. Roll back with `PATCH /api/workspaces/{workspace_id}/feature-flags` if quarantine growth started after enabling safety pipeline v2.
6. Release quarantine only through the admin override flow, with an operator reason. Do not bulk-clear DB rows.
7. Recover when the fraction stays below 0.1 for 1h and new block reasons match baseline.

## GgrWeakBucketGrowth

Severity: warning.

1. Compare weak GGR growth against recent imports, bought-account onboarding, and warmup completion.
2. Check whether the weak growth is concentrated in one workspace, strategy, proxy provider, or account origin.
3. Inspect recent safety-gate verdict samples for `ggr_too_low`, `profile_incomplete`, and `status_degraded`.
4. Hold new risky execution for affected workspaces until GGR recalculation and warmup state look fresh.
5. Roll back with `PATCH /api/workspaces/{workspace_id}/feature-flags` if weak growth correlates with a new rollout and operators confirm false positives.
6. Recover when weak growth is below 5 accounts/hour for 1h and no correlated gate block burst remains active.

## GateBlockBurst

Severity: critical.

1. Treat as a possible workspace-wide safety regression. Stop rollout expansion immediately.
2. Confirm whether `safety_gate_blocks_total{reason="ggr_too_low"}` is isolated to one `workspace_id`, `intent`, or recent deployment.
3. Check GGR calculator freshness, recent migrations/backfills, and safety-policy preset changes.
4. If false positives are likely, disable `safety_pipeline_v2_enabled` only for affected workspaces through `PATCH /api/workspaces/{workspace_id}/feature-flags`.
5. Keep audit history intact. Do not delete gate, GGR, quarantine, or operation-log records.
6. Recover when block rate stays below 50/min for 15m and affected operators confirm normal account eligibility.

## SendDurationSlow

Severity: warning.

1. Split by `strategy` in Grafana and identify which send strategy exceeds p95 30s.
2. Check worker saturation, Redis/RQ queue depth, proxy latency, and flood-wait rate.
3. If human-behavior typing is the bottleneck, compare `human_behavior_typing_emit_total` outcomes and consider moving affected workspaces to a less aggressive execution window.
4. Do not bypass TDLib/live execution gates. Latency alerts are not approval for live behavior changes.
5. Roll back with `PATCH /api/workspaces/{workspace_id}/feature-flags` only when latency is caused by safety-pipeline reserve/gate behavior, not downstream Telegram or proxy latency.
6. Recover when p95 is below 30s for 30m and queue depth returns to baseline.

## Dashboard

Import `docs/grafana/safety-pipeline.json` into Grafana with a Prometheus data source. Required checks:

- `quarantine_active` is visible over time.
- GGR weak bucket growth is visible by workspace.
- Gate block burst and send p95 panels match the Alertmanager expressions.
- Workspace variable can isolate a single workspace without hiding global panels.
