# Sub-agent E - Data Integrity, Migration Safety, Cascade

Task: [#148](https://github.com/pinnnthreetriples/StylistTG/issues/148) - Task 42, Full safety pipeline audit.

Scope: dimensions 7 data integrity, 8 cascade/cleanup, 11 resource limits, 15 production readiness. Static/local review only. No live TDLib/Telegram, production DB, production Redis, dependency installs, or production migrations.

## Summary

Verdict for this slice: **CONDITIONAL-GO blocker present for production enablement**. Safety pipeline data tables have valid FK constraints, but account deletion/cascade semantics are not production-ready: new safety tables use restrictive FKs to `account.id`, are not mapped as `Account` relationships, and `delete_account()` does not clean them up.

Findings count: P0=0, P1=2, P2=4, P3=0.

## Audit Coverage

| Dimension | Status | Evidence |
| --- | --- | --- |
| 7 Data integrity | Issues found | FK/unique/check constraints inspected in `backend/app/models.py` and migrations `0035`-`0053`; backfill tests inspected. |
| 8 Cascade / cleanup | Issue found | `delete_account()` cleanup compared against safety tables and FK `ondelete` settings. |
| 11 Resource limits | Issues found | DB engine, Redis clients, webhook notifier, rate-limit persistence, and migration lint inspected. |
| 15 Production readiness | Issues found | Feature-flag rollback path, migration downgrade/replay path, and backfill reversibility inspected. |

## Replay Blocker / Fallback

Full migration replay against a staging-size database was **not run**. Phase 0 already records `prometheus_client` missing for full pytest collection, and this sub-agent had no approved synthetic/staging PostgreSQL dataset with >=10k accounts. Running `alembic downgrade base` against the configured database would be destructive and violates the no production/staging-side-effect constraint.

Fallback evidence used:

```powershell
rtk proxy powershell -NoProfile -Command "Get-ChildItem backend/migrations/versions -Filter *.py"
rtk proxy powershell -NoProfile -Command "Select-String -Path backend/migrations/versions/*.py -Pattern 'ForeignKeyConstraint|ForeignKey|ondelete|def downgrade|op.execute|create_index'"
rtk proxy powershell -NoProfile -Command "python backend/tools/migration_lint.py --paths (Get-ChildItem backend/migrations/versions -Filter *.py | ForEach-Object { $_.FullName })"
```

## Findings

### F-E001: Account deletion is blocked by new safety-pipeline FK rows

**Severity**: P1  
**Dimension**: 7 Data integrity; 8 Cascade / cleanup  
**Affected**: `backend/app/services/accounts.py:130`, `backend/app/models.py:283`, `backend/app/models.py:320`, `backend/app/models.py:353`, `backend/app/models.py:392`, `backend/app/models.py:427`, `backend/migrations/versions/20260520_0036_account_ggr_scores.py:63`, `backend/migrations/versions/20260520_0045_cross_module_load_buckets.py:45`  
**Found by**: static FK/cascade review

**Description**: Safety tables `account_ggr_scores`, `account_behavior_profile`, `account_quarantines`, `account_status_observations`, `cross_module_load_buckets`, and `bought_onboarding_state` all reference `account.id` without `ON DELETE CASCADE`. `Account` does not define ORM relationships for these tables, and `delete_account()` only deletes terminal jobs and `AccountAuthAttempt` before `session.delete(account)`.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "Select-String -Path 'backend/app/models.py','backend/migrations/versions/20260520_*.py' -Pattern 'AccountQuarantine|AccountStatusObservation|CrossModuleLoadBucket|AccountGgrScore|AccountBehaviorProfile|ForeignKey\\(\"account.id\"\\)|ForeignKeyConstraint\\(\\[\"account_id\"\\], \\[\"account.id\"\\]' -Context 0,2"
# Expected: account-owned safety tables either have ON DELETE CASCADE, ORM delete-orphan relationships, or explicit cleanup in delete_account().
# Actual: restrictive/default FKs and no delete_account cleanup for safety tables.
```

**Impact**: Deleting an account with safety-pipeline artifacts can fail at commit with FK violations. GDPR-style hard delete/right-to-be-forgotten workflows are not reliable after enabling safety pipeline v2.

**Suggested fix**: Pick one account lifecycle policy and encode it consistently: DB-level `ondelete="CASCADE"` for per-account derived safety tables, or explicit `delete()` cleanup in `delete_account()` plus regression tests covering all safety tables. Document retained audit/event tables separately if they intentionally outlive accounts.

**Effort estimate**: M

### F-E002: Migration replay and downgrade reversibility are not proven

**Severity**: P1  
**Dimension**: 15 Production readiness  
**Affected**: migration chain `20260423_0001` through `20260523_0053`, `docs/audits/2026-05-safety-pipeline-audit/00-setup.md:44`  
**Found by**: setup audit + static migration review

**Description**: Phase 0 confirms 49 migration files and one Alembic head, but no upgrade/downgrade replay log exists for a synthetic/staging-size dataset. The requested production-readiness check (`upgrade head -> downgrade base -> upgrade head`) is destructive without a disposable DB and was not safe to run in this sub-agent.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "Get-Content docs/audits/2026-05-safety-pipeline-audit/00-setup.md | Select-String 'Migration files|Alembic heads|prometheus_client'"
# Expected: replay evidence for every migration on synthetic/staging-size DB.
# Actual: only file count and single-head evidence; replay blocked by missing safe disposable DB.
```

**Impact**: Production rollout cannot rely on downgrade/rollback safety. Data-shape regressions or lock-heavy migrations may only surface during deployment.

**Suggested fix**: Add a disposable Postgres replay job that seeds >=10k synthetic accounts and all safety tables, runs `alembic upgrade head`, `alembic downgrade base`, and `alembic upgrade head`, then stores timing/count deltas in `11-migration-replay-log.md`.

**Effort estimate**: M

### F-E003: Large-table migrations lack online-schema rollout notes

**Severity**: P2  
**Dimension**: 11 Resource limits; 15 Production readiness  
**Affected**: `backend/migrations/versions/20260520_0043_account_quarantine.py:46`, `20260520_0044_account_status_observations.py:45`, `20260520_0045_cross_module_load_buckets.py:55`, `20260520_0046_account_origin.py:25`, `20260520_0048_account_terminal_status.py:21`, `20260520_0049_attempt_idempotency_keys.py:39`, `20260522_0052_account_safety_grace_period.py:21`  
**Found by**: migration linter

**Description**: Existing migration linter flags large-table `add_column`, `create_index`, `create_unique_constraint`, and `create_check_constraint` operations when they lack an `# expected: requires online schema change` note. Safety-pipeline migrations add account columns and create indexes on high-growth event/bucket tables without rollout documentation.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "python backend/tools/migration_lint.py --paths (Get-ChildItem backend/migrations/versions -Filter *.py | ForEach-Object { $_.FullName })"
# Expected: no warnings for migration rollout safety, or explicit online-schema comments.
# Actual: warnings for account, account_quarantines, account_status_observations, cross_module_load_buckets, neuro_comment_events, and account safety columns.
```

**Impact**: Production migration may take heavyweight locks or cause slow deploys as table sizes grow. This is especially relevant before enabling a pipeline expected to increase observation/load/event write volume.

**Suggested fix**: Add per-migration rollout notes or split high-risk operations into online/concurrent-safe steps where supported. Ensure CI treats new large-table warnings as release-blocking for future safety migrations.

**Effort estimate**: S

### F-E004: Runtime DB/Redis clients lack explicit timeout caps in hot paths

**Severity**: P2  
**Dimension**: 11 Resource limits; 15 Production readiness  
**Affected**: `backend/app/db.py:13`, `backend/app/services/safety_gate_cache.py:45`, `backend/app/services/account_safety_gate.py:520`, `backend/app/services/safety_gate_reserve.py:174`, `backend/app/job_queue/rq.py:68`, `backend/app/services/scheduler.py:119`  
**Found by**: static resource-limit review

**Description**: The SQLAlchemy engine config sets `pool_pre_ping`, `pool_size`, and `max_overflow`, but no `pool_timeout`, `connect_timeout`, or statement timeout is configured. Several Redis hot paths use `Redis.from_url(settings.redis_url)` without socket connect/read timeouts; diagnostics paths do set short Redis timeouts, proving the pattern exists but is not applied consistently.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "Select-String -Path 'backend/app/db.py','backend/app/**/*.py' -Pattern 'create_engine\\(|pool_timeout|connect_timeout|statement_timeout|Redis\\.from_url\\(settings.redis_url|socket_timeout' -Context 0,3"
# Expected: bounded DB pool wait/connect/query behavior and bounded Redis socket behavior in gate/queue/scheduler paths.
# Actual: DB engine lacks timeout settings; gate cache/reserve, RQ queues, scheduler flush use Redis clients without socket timeouts.
```

**Impact**: During DB or Redis degradation, safety gate evaluation, scheduler ticks, and enqueue paths can hang longer than intended instead of failing fast or degrading predictably.

**Suggested fix**: Add settings for DB `pool_timeout`, Postgres connect timeout/options statement timeout, and Redis socket timeouts. Apply them to shared Redis factory code so gate, scheduler, and RQ paths share one bounded client construction path.

**Effort estimate**: M

### F-E005: Backfill behavior seed is not stable across Python processes

**Severity**: P2  
**Dimension**: 7 Data integrity; 15 Production readiness  
**Affected**: `backend/scripts/backfill_safety_pipeline.py:190`, `backend/tests/scripts/test_backfill_safety_pipeline.py:46`, `backend/tests/scripts/test_backfill_safety_pipeline.py:87`  
**Found by**: static backfill review

**Description**: `_stable_seed(account_id)` uses Python's built-in `hash(account_id)`, which is randomized per interpreter process by default. The backfill is idempotent once a row exists, but first-run generated behavior profiles are not deterministic across replay environments.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "Select-String -Path 'backend/scripts/backfill_safety_pipeline.py','backend/tests/scripts/test_backfill_safety_pipeline.py' -Pattern '_stable_seed|hash\\(|test_backfill_is_idempotent' -Context 0,3"
# Expected: stable per-account seed derived from deterministic hash (for example SHA-256 prefix).
# Actual: seed uses process-randomized Python hash().
```

**Impact**: Synthetic replay, restore/rebuild, or partial backfill reruns can produce different account behavior baselines for the same account IDs. This weakens reproducibility for audit and rollback validation.

**Suggested fix**: Replace `hash(account_id)` with deterministic hashing (`hashlib.sha256(account_id.encode()).digest()` converted to an int) and add a test with a fixed expected seed value.

**Effort estimate**: S

### F-E006: Nullable typing-speed downgrade is data-lossy

**Severity**: P2  
**Dimension**: 15 Production readiness  
**Affected**: `backend/migrations/versions/20260520_0038_account_behavior_profile_nullable_typing.py:32`  
**Found by**: static downgrade review

**Description**: Migration `0038` allows `account_behavior_profile.typing_speed_baseline_cpm` to be `NULL` for aggressive mode. Its downgrade rewrites all `NULL` values to `120` before making the column non-nullable, losing the information that typing simulation was intentionally disabled.

**Reproduction**:

```powershell
rtk proxy powershell -NoProfile -Command "Get-Content backend/migrations/versions/20260520_0038_account_behavior_profile_nullable_typing.py"
# Expected: downgrade limitation documented, or reversible encoding preserving NULL/aggressive intent.
# Actual: downgrade UPDATE converts NULL typing speeds to 120.
```

**Impact**: If production rollback crosses this migration after aggressive profiles exist, behavior settings silently change. That violates the audit's requested data-level reversibility bar.

**Suggested fix**: Document downgrade as intentionally lossy and include it in rollback runbooks, or add a reversible marker before downgrade if rollback across `0038` is a supported production path.

**Effort estimate**: S

## No-Issue Checks

- FK constraints exist for safety tables; invalid account/workspace inserts should be rejected by DB constraints. Evidence: `AccountGgrScore`, `AccountBehaviorProfile`, `AccountQuarantine`, `AccountStatusObservation`, `CrossModuleLoadBucket`, and `RateLimitPersistentCounter` all declare FKs in models/migrations.
- Uniqueness constraints exist for one-row-per-account derived state: `uq_account_ggr_scores_ws_account`, `uq_account_behavior_profile_ws_account`, `uq_cross_module_load_buckets_ws_account_bucket`, and `uq_rate_limit_persistent_counters_scope_window`.
- Backfill artifact creation is idempotent for existing GGR/behavior rows. Evidence: `backend/tests/scripts/test_backfill_safety_pipeline.py:87`.
- Backfill respects workspace filter. Evidence: `backend/tests/scripts/test_backfill_safety_pipeline.py:173`.
- Retention worker is idempotent for its configured retention targets. Evidence: `backend/app/services/retention_worker.py:30` and `backend/tests/test_retention_worker.py:210`.
- Feature flag default is off and the gate checks the flag before v2 cache lookup, so disabling the flag should route to legacy shim without needing cache invalidation. Evidence: `backend/app/services/account_safety_gate.py:88`, `backend/tests/test_safety_pipeline_feature_flags.py:37`, `backend/tests/test_account_safety_gate_legacy_shim.py:24`.
- Webhook delivery has an explicit timeout default (`5.0s`). Evidence: `backend/app/services/notification_channels/webhook.py:13`.

## Open Questions For Orchestrator

- Should audit/sensitive event tables intentionally retain account IDs after account deletion, or should they redact/null account references? Current safety derived tables appear account-owned, but audit retention policy needs product/legal confirmation.
- Is rollback across `20260520_0038` considered supported after production profiles exist? If not, final verdict should state that downgrade below `0038` is unsupported once safety v2 has generated behavior profiles.
