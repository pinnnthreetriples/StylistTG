# Coverage Gap Report

This report combines test execution evidence and audit confidence for critical-path services. It is not a `pytest-cov` percentage report because full local collection is blocked by missing `prometheus_client`.

| Service / surface | Existing evidence | Gap | Risk | Follow-up |
| --- | --- | --- | --- | --- |
| `account_safety_gate.py` | Unit/integration tests exist; targeted analyzer passed | Full collection blocked; E2E call-count assertion is self-fulfilling | P2 | Replace synthetic call loop with workflow-driven gate call assertions. |
| `ggr_calculator.py` | `test_ggr_calculator.py`: 49 passed | Workspace-mismatch tests missing for warmup/profile inputs | P1 | Add mismatched workspace rows and assert ignored. |
| `account_quarantine.py` | `test_account_quarantine.py`: 13 passed | Active overlapping quarantine/idempotency not covered | P2 | Add repeated/concurrent create tests. |
| `sender_service.py` | Static review found failure-path gaps | Sender test command did not complete before checkpoint; non-flood error path not proven | P1 | Add tests for non-flood `TelegramCommentSendError` and unexpected exception cleanup. |
| `reconcile_stuck_attempts.py` | Tests noted for found/missing/recent/error cases | Inconsistent observed/target/campaign workspace rows not covered | P2 | Add corrupt-row recovery tests. |
| `account_status_monitor.py` | Existing monitor tests and E2E scenarios | Unbounded global tick/duplicate scheduler runs not covered | P2 | Add limit/lock tests after design change. |
| `safety_gate_reserve.py` | Unit tests encode fail-open and concurrency behavior | Redis-down live-send policy and expired reservation counter not covered as rollout blockers | P1/P2 | Add Redis outage and TTL-expiry tests. |
| `safety_metrics.py` / Grafana | Metrics tests exist but require `prometheus_client`; JSON parses | Local test env blocked; dashboard query not validated against emitted names | P1/P2 | Dependency fix + dashboard PromQL name validator. |
| `backfill_safety_pipeline.py` | Sequential idempotency and workspace filter tests exist | Concurrent backfill race and deterministic seed not covered | P2 | Add duplicate planned-action/upsert tests and fixed seed test. |
| Account deletion / cascade | No evidence of safety-table delete coverage | Account delete with safety artifacts likely untested | P1 | Add account deletion integration test covering all safety tables. |

## Coverage Threshold Assessment

Requested thresholds were critical-path >=80% and others >=60%. Because full coverage could not run, this audit cannot certify numeric thresholds. The practical confidence level is:

- Gate/GGR/quarantine: enough targeted coverage for current happy paths, but missing edge cases above.
- Sender/reconcile/status monitor: needs failure/corrupt/concurrent coverage before live rollout.
- Observability/migration/data lifecycle: not coverage-certified; requires dedicated verification jobs.
