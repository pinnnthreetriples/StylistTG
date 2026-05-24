# Phase 4 Roadmap

## Strategic Items

| Priority | Item | Why | Candidate source |
| --- | --- | --- | --- |
| P1 | Safety degraded-mode hardening | Redis and DB degradation must preserve safety guarantees under incident conditions. | F-301, F-305, F-E004 |
| P1 | Account lifecycle and retention policy | Account deletion, audit retention, and safety derived tables need one explicit product/legal stance. | F-E001 |
| P1 | Migration replay automation | Production rollout needs repeatable upgrade/downgrade evidence, not ad hoc confidence. | F-E002 |
| P1 | PII redaction hardening | Audit logs become production operator artifacts; PII must be masked. | B F-001 |
| P2 | End-to-end safety invariant tests | Workflow-driven gate assertions catch drift between modules better than helper-call counts. | F-042 |
| P2 | Observability correctness pass | Dashboard/runbook/metric drift should be caught automatically. | F-302, F-304 |
| P2 | Workspace-scoped admin controls | Admin safety override should be tenant-obvious in schema and static tooling. | B F-002/B F-003 |
| P2 | Behavior-aware live sender integration decision | Decide whether human behavior emulator is required for rollout or a later product feature. | F-008 |
| P2 | Scheduler scalability | Status monitor needs production-scale batching/locking before larger workspace rollout. | F-006 |
| P3 | API-client generation hygiene | Prefer generated OpenAPI methods for safety endpoints to reduce drift. | F-006-003 |

## Suggested Sequencing

1. Close P1 safety/data/security conditions.
2. Run disposable migration replay and Task 40 preflight.
3. Canary one workspace for 48h with fixed observability.
4. Address P2 test/observability/scheduler hardening before 10% rollout.
5. Defer behavior-aware sender only if rollout docs explicitly state scope.

## Success Criteria For Phase 4

- No P1 audit finding remains open for live-send production enablement.
- `14-production-readiness-verdict.md` can be updated from `CONDITIONAL-GO` to `GO`.
- Canary has 48h of clean safety metrics, no quarantine-ratio blind spots, and no stuck-attempt growth.
- Follow-up issues have owners and board status.
