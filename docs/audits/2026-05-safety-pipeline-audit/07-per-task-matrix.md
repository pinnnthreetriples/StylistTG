# Per-task Matrix

Legend: `A` = approved/no material issue in this audit slice, `F` = finding applies, `G` = gap/unverified, `N` = not primary for task.

Dimensions: D1 spec, D2 tenancy, D3 security, D4 concurrency, D5 failure, D6 time, D7 data, D8 cascade, D9 tests, D10 code, D11 limits, D12 logging, D13 performance, D14 observability, D15 prod readiness, D16 frontend, D17 integration, D18 docs.

| Task | Status | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 | D11 | D12 | D13 | D14 | D15 | D16 | D17 | D18 | References |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 enum-shelfware | APPROVE | A | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | A | N | No direct finding. |
| 2 AI provider env validation | APPROVE | A | N | A | N | A | N | N | N | A | A | N | A | N | N | A | N | A | N | No direct finding. |
| 3 approval expirer | APPROVE | A | N | A | N | A | F | N | N | A | A | N | A | N | N | A | N | A | N | Time style: F-006-004/F-007. |
| 4 UI routes + wizard | APPROVE | A | N | N | N | N | N | N | N | A | A | N | N | N | N | A | A | A | A | F-agent checks. |
| 5 smoke pipeline + fake TDLib | NEEDS_FIX | A | A | N | N | A | A | N | N | F | N | N | N | N | N | G | N | F | N | Self-fulfilling gate coverage pattern appears in later E2E: F-042. |
| 6 pinned channel operation | APPROVE | A | N | N | N | N | N | N | N | A | A | N | A | N | N | A | A | A | N | No direct finding. |
| 7 bulk-import targets | APPROVE | A | A | A | N | A | N | N | N | A | A | N | A | N | N | A | A | A | N | No direct finding. |
| 8 prompt presets | APPROVE | A | N | N | N | N | N | N | N | A | A | N | N | N | N | A | A | A | N | No direct finding. |
| 9 safety preset limits | APPROVE | A | N | N | N | N | N | N | N | A | A | N | N | N | N | A | A | A | A | No direct finding. |
| 10 WorkspaceSafetyPolicy | APPROVE | A | A | A | N | A | N | A | N | A | A | N | A | N | N | A | A | A | A | Sensitive audit present; no direct blocker. |
| 11 GGR Calculator | NEEDS_FIX | A | F | N | N | N | F | F | N | A | F | N | N | F | F | F | N | F | A | F-003, F-304, F-E002, F-006-004, F-007. |
| 12 AccountQuarantine | NEEDS_FIX | A | A | A | F | A | N | F | F | A | A | N | A | N | F | F | A | F | A | F-005, F-302, F-303, F-E001. |
| 13 AccountSafetyGate | NEEDS_FIX | A | A | N | F | F | F | A | N | F | F | F | A | F | F | F | A | F | A | F-042, F-043, F-305, F-006-004, F-007. |
| 14 HumanBehaviorEmulator | GAP | F | N | N | N | N | N | N | N | A | A | N | N | N | A | G | N | F | F | Behavior not wired into live sender: F-008. |
| 15 AccountStatusMonitor | NEEDS_FIX | A | A | N | F | A | A | A | N | A | A | F | A | F | A | F | N | A | A | F-006. |
| 16 Profile completeness | APPROVE | A | A | N | N | A | N | A | N | A | A | N | N | N | N | A | A | A | A | No direct finding. |
| 17 CrossModuleLoadTracker | APPROVE | A | A | N | A | A | A | A | F | A | A | N | N | A | A | A | N | A | A | Cascade risk covered by F-E001. |
| 18 Bought-account onboarding | APPROVE | A | A | A | N | A | A | A | F | A | A | N | A | N | N | A | A | A | A | Cascade risk covered by F-E001. |
| 19 Gate integration | NEEDS_FIX | A | A | N | F | F | N | N | N | F | A | F | A | F | A | F | A | F | A | F-001, F-002, F-042, F-043, F-008. |
| 20 Feature flag v2 | APPROVE | A | A | A | N | A | N | A | N | A | A | N | A | N | N | A | A | A | A | No direct blocker; rollback smoke noted. |
| 21 Attempt idempotency | APPROVE | A | A | N | A | A | N | A | N | A | A | N | A | N | N | A | N | A | A | DB uniqueness verified by B. |
| 22 Redis Lua reserve | NEEDS_FIX | A | N | N | F | F | N | N | N | A | A | F | N | F | F | F | N | F | A | F-002, F-301, F-305, F-004. |
| 23 Persistent rate limiter | NEEDS_FIX | A | A | N | A | F | N | A | N | A | A | F | A | F | N | F | N | A | A | F-002, F-E004. |
| 24 Reconcile stuck attempts | NEEDS_FIX | A | F | N | A | F | N | A | N | A | A | N | A | N | A | A | N | F | A | F-004. |
| 25 Tenant scope | NEEDS_FIX | A | F | N | N | N | N | A | N | G | A | N | N | N | N | F | N | A | A | F-002, F-003; semgrep unavailable. |
| 26 Sensitive audit | NEEDS_FIX | A | A | F | N | N | N | A | N | A | A | N | A | N | N | F | N | A | A | F-001. |
| 27 Gate perf budget | NEEDS_FIX | A | N | N | F | F | N | N | N | A | A | F | N | F | F | F | N | F | A | F-305, F-306. |
| 28 Backfill strategy | NEEDS_FIX | A | A | N | F | A | N | F | N | A | A | N | N | N | N | F | N | A | A | F-005, F-E005. |
| 29 Migration safety | NEEDS_FIX | A | N | N | N | N | N | F | F | G | A | F | N | N | N | F | N | A | A | F-E002, F-E003, F-E006. |
| 30 Observability | NEEDS_FIX | A | N | N | N | N | N | N | N | G | A | N | N | F | F | F | N | A | F | F-302, F-303, F-304, F-306. |
| 31 Admin notifications | APPROVE | A | A | A | N | A | N | N | N | A | A | N | A | N | F | A | A | A | A | GGR drop TODO noted, no blocker. |
| 32 Manual quarantine/admin override | NEEDS_FIX | F | F | A | N | A | A | A | F | A | A | N | A | N | N | F | F | F | A | F-006-001, F-002, F-003, F-E001. |
| 33 Terminal status enum | APPROVE | A | A | A | N | A | N | A | N | A | A | N | A | N | N | A | A | A | A | No direct finding. |
| 34 Disaster mode UI | APPROVE | A | A | A | N | A | N | N | N | A | A | N | A | N | A | A | A | A | A | Targeted UI tests passed. |
| 35 Edit-diff audit | NEEDS_FIX | A | A | F | N | N | N | A | N | A | A | N | A | N | N | F | A | A | A | Redaction gap applies: F-001. |
| 36 Retention | APPROVE | A | A | A | N | A | A | A | A | A | A | N | A | N | N | A | N | A | A | Retention no-issue checks by B/E. |
| 37 Behavior property tests | GAP | A | N | N | N | N | N | N | N | A | A | N | N | N | N | G | N | F | A | Behavior not live-wired: F-008. |
| 38 Extended E2E pipeline | NEEDS_FIX | A | A | N | A | A | A | A | N | F | A | N | N | N | N | G | N | F | A | F-042, Phase 0 dependency gap. |
| 39 Safety docs | NEEDS_FIX | A | N | N | N | N | N | N | N | N | N | N | N | N | F | F | N | A | F | F-302, F-304, F-006-002. |
| 40 Production preflight | NEEDS_FIX | A | A | A | F | F | N | F | F | G | A | F | A | F | F | F | A | F | A | Conditions in verdict. |
| 41 GGR cleanup + threshold | NEEDS_FIX | A | F | N | N | N | F | F | N | A | A | N | N | F | F | F | N | F | A | PR #149; F-003/F-304/F-007 still apply. |

## Matrix Summary

- `APPROVE`: 18 tasks have no material blocking finding in this audit pass.
- `NEEDS_FIX`: 21 tasks have at least one linked P1/P2 finding or rollout condition.
- `GAP`: 2 tasks are implemented as foundation/test coverage but not proven end-to-end for live behavior.
- The strongest blockers are cross-task: live sender failure cleanup, Redis fail-open/degraded behavior, account deletion/cascade, migration replay proof, PII redaction, and observability metric drift.
