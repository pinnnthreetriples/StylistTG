# Sub-agent B: Tenancy + Security + Concurrency Findings

Task: [#148](https://github.com/pinnnthreetriples/StylistTG/issues/148) - Task 42 full safety pipeline audit.

Scope: dimensions 2 tenant isolation, 3 security, and 4 concurrency across safety-pipeline Tasks 1-41. Production code, tests, config, secrets, TDLib runtime data, prod DB, prod Redis, and dependency installs were not touched.

Note: the local spec artifact `docs/superpowers/plans/2026-05-19-three-module-integration-and-account-safety.md` contains labeled Tasks 1-40. I also checked `rtk git log --oneline --grep="Task 41\|task 41\|task-41" -10`; it returned no local commit labels. This file therefore audits the available Task 1-40 implementation plus Task-41-adjacent safety artifacts visible in code.

## Summary

Findings count: P0 0, P1 1, P2 4, P3 0.

Overall for this slice: no P0 blocker found in the reviewed tenancy/security/concurrency paths. Main rollout risk is incomplete PII redaction in sensitive audit/log metadata. Remaining issues are defense-in-depth gaps around tenant static analysis, workspace ownership on safety overrides, Lua crash cleanup semantics, and concurrent backfill idempotency.

## Findings

### F-001: Sensitive redaction misses email and phone PII

**Severity**: P1
**Dimension**: 3 Security
**Affected**: `backend/app/services/secret_redaction.py:7`, `backend/app/services/secret_redaction.py:23`, `backend/app/services/sensitive_audit.py:44`, `backend/app/services/sensitive_audit.py:48`
**Found by**: `rtk python -c "from app.services.secret_redaction import redact_text, redact_metadata; print(redact_text('contact user@example.test phone +15550102000 token=abc')); print(redact_metadata({'email':'user@example.test','phone':'+15550102000','token':'abc'}))"` from `backend/`

**Description**: Sensitive audit events sanitize token-like fields, but the redactor does not treat `email` or `phone` as sensitive keys and does not redact email/phone patterns inside strings. Task 42 dimension 3 explicitly calls out PII redaction for email and phone. `record_sensitive_audit_event()` relies on this helper for reasons and metadata, so any future or existing admin mutation metadata containing contact PII is persisted and returned unmasked by audit APIs.

**Reproduction**:

```bash
cd backend
rtk python -c "from app.services.secret_redaction import redact_text, redact_metadata; print(redact_text('contact user@example.test phone +15550102000 token=abc')); print(redact_metadata({'email':'user@example.test','phone':'+15550102000','token':'abc'}))"
# Expected: email and phone are masked, token is masked.
# Actual: contact user@example.test phone +15550102000 token=***
# Actual: {'email': 'user@example.test', 'phone': '+15550102000', 'token': '***'}
```

**Impact**: Admin audit rows, operation metadata, Sentry/log sanitizers that reuse this helper, and audit API responses can retain phone numbers or email addresses. That is a security/privacy gap before production rollout.

**Suggested fix**: Add email and phone key fragments plus conservative regex redaction for email/E.164-like phone values in `secret_redaction.py`. Add regression coverage for `record_sensitive_audit_event()` metadata/reason strings and any audit API response serialization.

**Effort estimate**: S

### F-002: Tenant static rule does not cover AccountSafetyOverride

**Severity**: P2
**Dimension**: 2 Tenant isolation
**Affected**: `.semgrep/tenant_scope.yaml:22`, `backend/app/models.py:1999`, `backend/app/services/account_safety_overrides.py:71`, `backend/app/services/account_safety_overrides.py:94`
**Found by**: `rtk rg -n "AccountSafetyOverride|missing-workspace-id-filter" .semgrep/tenant_scope.yaml backend/app/models.py backend/app/services/account_safety_overrides.py`

**Description**: The tenant Semgrep allowlist includes safety-pipeline models such as `AccountQuarantine`, `AccountStatusObservation`, `CrossModuleLoadBucket`, and `AccountGgrScore`, but omits `AccountSafetyOverride`. The override service queries active overrides by `account_id` only. Current route creation checks the account workspace first, so this is not an observed cross-tenant exploit, but the static guard required by Task 25 will not catch future unscoped override queries.

**Reproduction**:

```bash
rtk rg -n "AccountSafetyOverride|missing-workspace-id-filter" .semgrep/tenant_scope.yaml backend/app/models.py backend/app/services/account_safety_overrides.py
# Expected: AccountSafetyOverride appears in the Semgrep tenant model regex, and service queries include workspace_id or equivalent guard.
# Actual: model exists at backend/app/models.py:1999; semgrep regex omits it; active override queries filter only account_id/allowed_until.
```

**Impact**: Future safety override endpoints or batch flows could add account-id-only lookups without CI/static analysis catching them. Safety overrides are admin/operator security controls, so tenant drift here can affect moderation decisions.

**Suggested fix**: Add `AccountSafetyOverride` to `.semgrep/tenant_scope.yaml` and its synthetic tests. Prefer adding `workspace_id` to the table/service contract, or make the account join/workspace predicate explicit where active overrides are read.

**Effort estimate**: S-M

### F-003: AccountSafetyOverride rows are not workspace-scoped

**Severity**: P2
**Dimension**: 2 Tenant isolation
**Affected**: `backend/app/models.py:1999`, `backend/app/services/account_safety_overrides.py:25`, `backend/app/services/account_safety_overrides.py:71`, `backend/app/services/account_safety_overrides.py:94`
**Found by**: Semble search `tenant isolation workspace_id safety pipeline queries` plus `rtk rg -n "class AccountSafetyOverride|active_overrides_by_operation|batch_active_overrides_by_operation" backend/app`

**Description**: `AccountSafetyOverride` has `account_id`, `operation`, and `allowed_until`, but no `workspace_id` column or workspace-aware unique/index contract. Creation checks `get_account(..., workspace_id=...)`, yet reads are later by `account_id` only. The safety-pipeline tenant rule in Task 25 says new safety tables should be tenant-scoped; this table is a safety/admin-control table and does not meet that standard directly.

**Reproduction**:

```bash
rtk rg -n "class AccountSafetyOverride|workspace_id|active_overrides_by_operation|batch_active_overrides_by_operation" backend/app/models.py backend/app/services/account_safety_overrides.py
# Expected: AccountSafetyOverride stores workspace_id and active override queries filter by it, or the table is explicitly documented as account-owned with enforced account join.
# Actual: no workspace_id column on the model; active queries use account_id and allowed_until only.
```

**Impact**: The current UUID account-id design lowers practical risk, but the data model does not make tenancy self-evident or statically enforceable. This increases future regression risk around manual safety overrides and batch safety previews.

**Suggested fix**: Add `workspace_id` to `account_safety_override` with a backfill from account, index `(workspace_id, account_id, operation, allowed_until)`, then thread workspace predicates through override reads. If migration is deferred, document the account-owned tenancy invariant and add a regression test proving foreign workspace account IDs cannot affect override decisions.

**Effort estimate**: M

### F-004: Lua reservation counter can remain inflated after reservation TTL expires

**Severity**: P2
**Dimension**: 4 Concurrency correctness
**Affected**: `backend/app/services/safety_gate_reserve.py:46`, `backend/app/services/safety_gate_reserve.py:48`, `backend/app/services/safety_gate_reserve.py:50`, `backend/app/services/safety_gate_reserve.py:63`
**Found by**: Semble search `Redis Lua safety gate reserve concurrency release stale verdict reserve script`; line review of `backend/app/services/safety_gate_reserve.py`

**Description**: Reserve increments a shared counter and sets the per-reservation detail key with `ttl`; the counter key expires at `ttl * 2`. Release decrements only if the reservation detail key still exists. If a worker crashes or the reservation detail key expires before release, the counter remains inflated until the longer counter TTL expires.

**Reproduction**:

```bash
rtk rg -n "INCRBY|EXPIRE|SET.*reservation|GET.*reservation|DECRBY" backend/app/services/safety_gate_reserve.py
# Expected: crash cleanup decrements when a reservation expires, or counter TTL matches reservation TTL, or the counter is derived from live reservation keys.
# Actual: counter INCRBY at reserve; reservation key EX ttl; counter EX ttl*2; release returns 0 after reservation key expiry and does not decrement.
```

**Impact**: After a crash or long send, an account can be falsely blocked by `GATE_CONCURRENCY_LIMIT` for up to an extra reservation TTL window. This is fail-safe for sending volume, but can cause avoidable skips and noisy rollout alerts.

**Suggested fix**: Make reservation ownership and counter cleanup symmetric. Options: set counter TTL equal to reservation TTL, store reservations in a per-account set/zset and count live members, or make release decrement with a bounded floor when reservation ownership can be proven. Add a Redis/fakeredis test that advances past reservation TTL and confirms a new reserve is not falsely blocked.

**Effort estimate**: M

### F-005: Safety backfill has a check-then-insert race

**Severity**: P2
**Dimension**: 4 Concurrency correctness
**Affected**: `backend/scripts/backfill_safety_pipeline.py:102`, `backend/scripts/backfill_safety_pipeline.py:134`, `backend/scripts/backfill_safety_pipeline.py:150`, `backend/migrations/versions/20260520_0036_account_ggr_scores.py:66`, `backend/app/models.py:430`
**Found by**: Semble search `backfill safety pipeline idempotent race`; line review of backfill and unique constraints

**Description**: Backfill plans actions by checking whether GGR and behavior rows exist, then inserts later in the same batch. The unique constraints make repeated sequential runs idempotent, but two concurrent backfill invocations for the same workspace can both plan `ggr_created`/`behavior_created`; one then fails at commit with a uniqueness error instead of cleanly skipping.

**Reproduction**:

```bash
rtk rg -n "def _planned_actions|AccountGgrScore.id|AccountBehaviorProfile.id|AccountGgrScore\\(|AccountBehaviorProfile\\(" backend/scripts/backfill_safety_pipeline.py
# Expected: concurrent duplicate insert is handled with ON CONFLICT/IntegrityError retry or row locks.
# Actual: code checks existence, adds ORM rows, and relies on unique constraints at commit.
```

**Impact**: Production rollout runbooks can see a failed backfill if two operators/schedulers start the same workspace job. Data is protected by uniqueness constraints, but the run is not concurrency-idempotent and may require manual rerun/triage.

**Suggested fix**: Use dialect upsert/on-conflict-do-nothing for GGR and behavior inserts, or lock per workspace/backfill run before scanning. Add a test that simulates duplicate planned actions and asserts the second run exits successfully with skipped counts.

**Effort estimate**: M

## Explicit No-issue Checks

- Tenant scoping for main safety-pipeline read APIs looked correct in sampled routes: GGR, profile completeness, status observations, quarantine reads, and audit reads call `require_account_in_workspace()` or filter by `auth.workspace_id`.
- `.semgrep/tenant_scope.yaml` exists and includes synthetic positive/negative tests for missing workspace predicates in `.semgrep/tests/tenant_scope_test.py`. Semgrep CLI is not installed locally, so rule execution was not verified in this sub-agent run.
- Sensitive audit is present on reviewed admin mutations: safety policy patch, workspace feature flag patch, notification webhook patch, manual quarantine release, admin quarantine override, terminal status clear, and bought-account onboarding start.
- RBAC on reviewed admin endpoints is present: safety policy, workspace feature flags/notification settings, quarantine release/admin override/terminal clear, human behavior profile reads, and bought onboarding use `require_role("admin")`. Non-admin safety-policy regression coverage exists in `backend/tests/test_safety_policy_sensitive_audit.py:127`.
- Reconcile stuck attempts uses `with_for_update(skip_locked=True)` at `backend/app/services/reconcile_stuck_attempts.py:90`.
- Attempt idempotency has a DB uniqueness guard at `backend/app/models.py:1484` and migration `backend/migrations/versions/20260520_0049_attempt_idempotency_keys.py:30`.
- Quarantine retention deletes only released quarantine rows because `_delete_older_than(..., require_released=True)` adds `AccountQuarantine.released_at.is_not(None)`.

## Commands / Tools Used

- Serena `activate_project` and initial instructions.
- Semble semantic searches for tenant isolation, sensitive audit/RBAC, Redis Lua reserve, and reconcile/backfill/idempotency.
- `rtk rg` targeted static searches across `backend/app`, `backend/scripts`, `.semgrep`, and `backend/tests`.
- Direct line-number reads with PowerShell `Get-Content` for the affected files.
- Redaction smoke command shown in F-001.

## Inconclusive / Not Run

- `semgrep --config .semgrep/tenant_scope.yaml backend/` was not run because `semgrep` is not installed locally.
- A targeted pytest smoke (`rtk python -m pytest backend/tests/test_safety_policy_sensitive_audit.py backend/tests/infra/test_logging_utils.py::test_redact_metadata_redacts_secrets_inside_plain_string -q`) produced no output within the checkpoint window, so no pass/fail claim is made here.
- Task 41 was not separately identifiable from local spec headings or git log labels; see note at top.
