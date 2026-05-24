# Critical Path Findings

Sub-agent A scope: `backend/app/services/account_safety_gate.py`, `backend/app/services/ggr_calculator.py`, `backend/app/services/account_quarantine.py`, `backend/app/services/neuro_commenting/sender_service.py`, `backend/app/services/reconcile_stuck_attempts.py`, `backend/app/services/account_status_monitor.py`, plus behavior-sender equivalent lookup.

Behavior-sender note: no `behavior_aware_sender.py` exists. Semble and `rtk rg --files` found the production send equivalent at `backend/app/services/neuro_commenting/sender_service.py`; human-behavior modules are stubs under `backend/app/services/human_behavior/`.

## 1-Page Summary

Critical-path verdict for this sub-scope: **CONDITIONAL-GO for dry-run / shadow use, NO-GO for enabling live send without fixes to sender failure cleanup**.

Top risk: live sender failure handling is not consistently fail-closed. Non-flood `TelegramCommentSendError` leaves attempts in `SENDING`, and unexpected sender exceptions can skip reservation cleanup. Reconcile can repair some stuck attempts later, but that is delayed recovery, not immediate correctness.

Second risk: some critical-path reads rely on global IDs rather than workspace-constrained joins. Account IDs are globally unique in normal operation, so this is not an immediate cross-tenant exploit from reviewed callsites, but it weakens defense in depth and can produce wrong GGR/reconcile behavior if inconsistent rows exist after migration/backfill/operator scripts.

Tests/evidence run:

| Check | Result |
| --- | --- |
| `rtk python -m pytest backend/tests/test_ggr_calculator.py -q` | 49 passed in 3.60s |
| `rtk python -m pytest backend/tests/test_account_quarantine.py -q` | 13 passed in 22.02s |
| `rtk python -m pytest backend/tests/test_neuro_commenting_sender.py -q` | Started, no completion output before checkpoint; treated as incomplete |
| Line-numbered static review with `Get-Content` | Completed for all six critical services |
| Semble search | Confirmed sender equivalent and human-behavior stubs |

Finding count: **0 P0, 3 P1, 4 P2, 1 P3**.

## Findings

### F-001: Non-flood send errors leave attempts stuck in `SENDING`

**Severity**: P1
**Dimension**: 5 Failure modes / graceful degradation; 17 Integration coherence
**Affected**: `backend/app/services/neuro_commenting/sender_service.py:273`
**Found by**: Line-numbered static review, `rtk rg -n "FLOOD_WAIT|comment_send_failed|stuck_attempt_lost" backend/tests/test_neuro_commenting_sender.py backend/app/services/neuro_commenting/sender_service.py`

**Description**: `send_attempt()` catches `TelegramCommentSendError`, but only the `FLOOD_WAIT` branch calls `_mark_send_error()`. The non-flood branch rolls back reservations and sets `attempt.error_code` / `attempt.error_message`, but does not set `attempt.status = FAILED`, `failed_at`, health counters, or a failure event.

**Reproduction**:

```bash
rtk rg -n "except TelegramCommentSendError|attempt.error_code = exc.error_code|attempt.status = NeuroAttemptStatus.FAILED" backend/app/services/neuro_commenting/sender_service.py
# Expected: every caught send error transitions attempt to terminal/repairable state.
# Actual: lines 280-285 set error fields only; status remains SENDING from line 242.
```

**Impact**: Live send attempts can remain `SENDING` until reconcile runs. Operators see delayed or misleading state, rate/health feedback is delayed, and repeated errors can inflate stuck-attempt recovery load.

**Suggested fix**: Route all `TelegramCommentSendError` branches through `_mark_send_error()` or shared failure finalizer. Add regression test for a non-flood sender error such as `CHAT_NOT_FOUND`.

**Effort estimate**: S

### F-002: Unexpected sender exceptions can leak gate/rate reservations until TTL

**Severity**: P1
**Dimension**: 4 Concurrency correctness; 5 Failure modes / graceful degradation; 11 Resource limits
**Affected**: `backend/app/services/neuro_commenting/sender_service.py:221`, `backend/app/services/neuro_commenting/sender_service.py:264`
**Found by**: Static exception-path audit; `Get-Content` line review of sender and rate limiter.

**Description**: `send_attempt()` reserves rate and safety-gate slots before calling `send_comment()`, but cleanup happens only on success or `TelegramCommentSendError`. Any other exception class from TDLib adapter, metrics context, conversion, or dependency code bypasses `_rollback_reservation()` and `_release_gate_reservation()`.

**Reproduction**:

```bash
rtk rg -n "reserve_for_attempt|_try_gate_reserve|except TelegramCommentSendError|finally" backend/app/services/neuro_commenting/sender_service.py
# Expected: reservation cleanup in finally or broad finalizer after reservation is acquired.
# Actual: no finally exists; cleanup only occurs in TelegramCommentSendError branches and success path.
```

**Impact**: Account-level gate concurrency can remain consumed until `GATE_RESERVE_TTL_SECONDS=120`; rate-limit reservations can remain active until limiter TTL. This can block legitimate sends and distort safety metrics during adapter regressions.

**Suggested fix**: Wrap the send block in `try/except/finally`: rollback uncommitted rate reservations and release gate reservation for every non-success path, then re-raise or mark attempt failed according to error type.

**Effort estimate**: M

### F-003: GGR component reads are not consistently workspace constrained

**Severity**: P1
**Dimension**: 2 Tenant isolation; 7 Data integrity; 17 Integration coherence
**Affected**: `backend/app/services/ggr_calculator.py:212`, `backend/app/services/ggr_calculator.py:230`
**Found by**: `rtk rg -n "session.get\\(|select\\(" backend/app/services/ggr_calculator.py`; targeted test review.

**Description**: `_warmup_score()` selects latest `WarmupSession` by `account_id` only. `_profile_score()` uses `session.get(AccountProfileState, account.id)` where `AccountProfileState` has no workspace column. In normal data, `account.id` is globally unique, but DB constraints allow `WarmupSession.workspace_id` to disagree with the referenced account's workspace.

**Reproduction**:

```bash
rtk rg -n "_warmup_score|WarmupSession.account_id|_profile_score|AccountProfileState" backend/app/services/ggr_calculator.py backend/tests/test_ggr_calculator.py
# Expected: component reads either filter by account.workspace_id or are protected by composite FK/invariant tests.
# Actual: status observations have workspace-scope tests; warmup/profile component tests do not cover mismatched workspace rows.
```

**Impact**: A bad backfill, migration, or manual repair script can make GGR use another workspace's warmup/profile state. Since gate blocks on `ggr_score < 4.0`, wrong GGR can falsely allow or block live commenting.

**Suggested fix**: Filter `_warmup_score()` by `WarmupSession.workspace_id == account.workspace_id`. Add invariant tests for mismatched `WarmupSession.workspace_id`. For profile state, either document global account-id invariant or add workspace to `AccountProfileState` in a future migration.

**Effort estimate**: M

### F-004: Reconcile context loads related rows without campaign/workspace validation

**Severity**: P2
**Dimension**: 2 Tenant isolation; 5 Failure modes / graceful degradation; 17 Integration coherence
**Affected**: `backend/app/services/reconcile_stuck_attempts.py:183`
**Found by**: Line-numbered static review of `_load_context()`.

**Description**: `_load_context()` uses `session.get()` for campaign, observed post, and target by primary key. It then derives `workspace_id` from the campaign, but does not verify that the observed post and target belong to that campaign/workspace.

**Reproduction**:

```bash
rtk rg -n "def _load_context|session.get\\(NeuroCommentObservedPost|session.get\\(NeuroCommentTarget" backend/app/services/reconcile_stuck_attempts.py
# Expected: observed_post and target are loaded through repository helpers scoped by campaign/workspace.
# Actual: direct primary-key lookups allow inconsistent attempt rows to feed unrelated discussion_chat_id into reconcile.
```

**Impact**: If an attempt row is inconsistent, reconcile can search the wrong discussion chat, mark a send lost incorrectly, or attach the wrong Telegram message id. This is a recovery-path risk, not a normal-path exploit.

**Suggested fix**: Replace direct `session.get()` calls with repository helpers that constrain by campaign/workspace, or explicitly validate `observed.campaign_id == campaign.id` and `target.campaign_id == campaign.id`.

**Effort estimate**: S

### F-005: Quarantine creation allows overlapping active quarantines

**Severity**: P2
**Dimension**: 4 Concurrency correctness; 7 Data integrity; 14 Observability
**Affected**: `backend/app/services/account_quarantine.py:94`, `backend/app/models.py:283`
**Found by**: Static review of service and model constraints; `rtk python -m pytest backend/tests/test_account_quarantine.py -q`.

**Description**: `create_quarantine()` always inserts a new row and the model has only an index on `(workspace_id, account_id, until)`, not an active-row uniqueness guard. Repeated flood-wait handling or concurrent status-monitor ticks can create multiple active quarantines for the same account/reason.

**Reproduction**:

```bash
rtk rg -n "def create_quarantine|AccountQuarantine|ix_account_quarantines_ws_account_until|UniqueConstraint" backend/app/services/account_quarantine.py backend/app/models.py
# Expected: either idempotent reuse/extension of active quarantine or uniqueness/locking around active rows.
# Actual: every call inserts a new active quarantine when duration_hours > 0.
```

**Impact**: Gate still blocks because it picks one active row, but metrics and operator UI can overcount active risk. Admin release of one row may leave another active row, making recovery look broken.

**Suggested fix**: Make open quarantine idempotent per `(workspace_id, account_id, reason)` while active: extend `until` and merge metadata, or add a partial unique index where `released_at IS NULL` if product semantics allow only one active quarantine per reason.

**Effort estimate**: M

### F-006: Account status monitor tick is unbounded and lock-free

**Severity**: P2
**Dimension**: 4 Concurrency correctness; 11 Resource limits; 13 Performance & SLO
**Affected**: `backend/app/services/account_status_monitor.py:99`
**Found by**: Line-numbered static review.

**Description**: `tick()` scans every non-disabled account when `workspace_id` is omitted, ordered by `updated_at`, with no batch limit, checkpoint, or `skip_locked` discipline. The method writes observations and can auto-pause/quarantine inside the loop.

**Reproduction**:

```bash
rtk rg -n "def tick|select\\(Account\\)|order_by\\(Account.updated_at.asc\\(\\)\\)" backend/app/services/account_status_monitor.py
# Expected: production scheduler path has batch limit/checkpoint or single-runner lock.
# Actual: service method has no bound beyond workspace filter.
```

**Impact**: Large workspaces or accidental global ticks can generate long DB transactions, duplicate observations under concurrent schedulers, and delayed safety reactions for later accounts.

**Suggested fix**: Add `limit`, stable pagination/checkpoint, and scheduler-level singleton/lock. Consider `with_for_update(skip_locked=True)` if multiple monitor workers are intended.

**Effort estimate**: M

### F-007: Critical path uses mixed time sources instead of project `utc_now()`

**Severity**: P3
**Dimension**: 6 Time/timezone discipline; 10 Code quality
**Affected**: `backend/app/services/account_safety_gate.py:604`, `backend/app/services/ggr_calculator.py:67`, `backend/app/services/neuro_commenting/sender_service.py:375`
**Found by**: `rtk rg -n "datetime\\.now\\(|datetime\\.utcnow\\(" backend/app/services/account_safety_gate.py backend/app/services/ggr_calculator.py backend/app/services/neuro_commenting/sender_service.py backend/app/services/reconcile_stuck_attempts.py backend/app/services/account_status_monitor.py`

**Description**: Reviewed code uses aware `datetime.now(UTC)`, so this is not a naive-time bug. But project memory and models standardize on `utc_now()`, and several critical-path services mix direct `datetime.now(UTC)` with `utc_now()`.

**Reproduction**:

```bash
rtk rg -n "datetime\\.now\\(" backend/app/services/account_safety_gate.py backend/app/services/ggr_calculator.py backend/app/services/neuro_commenting/sender_service.py
# Expected: project-critical timestamp creation goes through utc_now().
# Actual: direct datetime.now(UTC) appears in gate age, GGR age, fake sender, send success/failure paths.
```

**Impact**: Low immediate production risk, but makes time-freezing and timestamp consistency easier to regress.

**Suggested fix**: Replace direct production timestamp calls with `utc_now()` where behavior is not intentionally wall-clock specific. Keep tests frozen around boundary windows.

**Effort estimate**: S

### F-008: Behavior-aware send is documented as future integration, not wired into live sender

**Severity**: P2
**Dimension**: 1 Spec compliance; 17 Integration coherence
**Affected**: `backend/app/services/human_behavior/typing_emulator.py:1`, `backend/app/services/human_behavior/typo_generator.py:1`, `backend/app/services/neuro_commenting/sender_service.py:264`
**Found by**: Semble search for behavior-aware sender; `rtk rg --files backend/app | rg "behavior_aware|sender|human_behavior"`.

**Description**: Human-behavior modules state that real TDLib integration happens in `behavior_aware_sender`, but no such file exists. `SenderService.send_attempt()` sends `final_text` directly through `TelegramCommentSender` without typing cadence, typo/correction, decoy actions, or action sequencing.

**Reproduction**:

```bash
rtk rg --files backend/app | rg "behavior_aware|sender|human_behavior"
rtk rg -n "emit_typing|maybe_typo|run_before_send|shuffle" backend/app/services/neuro_commenting/sender_service.py backend/app/services/human_behavior
# Expected: live sender invokes behavior emulator or docs/spec state foundation-only behavior.
# Actual: human_behavior modules are present, but sender_service has no callsites.
```

**Impact**: If issue #148 expects Task 42 to certify GramGPT-style live behavior, current sender is safety-gated but not behavior-aware. Live sends may be more automation-like than operators expect.

**Suggested fix**: Either wire a behavior-aware sender wrapper before enabling live sends, or explicitly scope rollout docs/readiness to "safety-gated direct sender, behavior emulator not live-wired yet".

**Effort estimate**: L

## Explicit No-Issue Statements By Dimension

| Dimension | Critical-path status |
| --- | --- |
| 1 Spec compliance | Gate, GGR, quarantine, status monitor, reconcile, and sender exist and match docs at a high level. Finding F-008 covers missing behavior-aware live wiring. Full 41-task compliance belongs to orchestrator/F-agent matrix. |
| 2 Tenant isolation | `account_safety_gate._account()`, quarantine reads/releases, status observations, and most sender repository loads are workspace-scoped. Findings F-003 and F-004 cover weaker paths. |
| 3 Security | No secrets/runtime data were read. Reviewed critical services do not log raw proxy host; status monitor stores hashes and presence booleans. Admin route RBAC was not deeply audited by this sub-agent. |
| 4 Concurrency correctness | Reconcile uses `with_for_update(skip_locked=True)`. Gate reserve uses Redis Lua embedded in `safety_gate_reserve.py`. Findings F-002/F-005/F-006 cover remaining critical risks. |
| 5 Failure modes | Gate has Redis cache fallback and cold-budget fail-closed behavior; reconcile handles TDLib search exceptions per account. Findings F-001/F-002/F-004 cover gaps. |
| 6 Time/timezone discipline | No naive `datetime.utcnow()` found in reviewed files. F-007 covers mixed `datetime.now(UTC)` vs `utc_now()`. |
| 7 Data integrity | Core GGR row has unique `(workspace_id, account_id)` and score/bucket checks. F-003/F-005 cover component and quarantine integrity risks. |
| 8 Cascade / cleanup | Account relationships include delete-orphan for several safety rows in `Account`, but `warmup_sessions` lacks cascade in the reviewed model excerpt. This needs E-agent migration/cascade pass; no separate A finding assigned. |
| 9 Test coverage | Targeted GGR and quarantine suites pass. Sender suite did not complete before checkpoint, so sender failure-path coverage remains unverified. |
| 10 Code quality | No broad lint run in this sub-agent scope. Static review found no `print()` in reviewed critical services. F-007 covers time-style inconsistency. |
| 11 Resource limits | Rate limiter and gate reserve have TTLs. F-002 and F-006 cover reservation leak and unbounded monitor tick. |
| 12 Logging quality | Reconcile uses structured `log_event` / `log_warn`; reviewed services avoid raw `print()`. `log_warn(..., error=str(exc))` may need B/C-agent PII review depending TDLib error contents. |
| 13 Performance & SLO | Gate cache and GGR recalc interval exist. No benchmark run. F-006 covers the most obvious unbounded critical-path scan. |
| 14 Observability | Gate, quarantine, GGR, status monitor, reconcile, and sender emit safety metrics/events in reviewed callsites. F-005 notes active-quarantine metric distortion from duplicates. |
| 15 Production readiness | Feature-flag legacy shim exists in `AccountSafetyGate.evaluate()`. Live send should wait for F-001/F-002. Migration replay/backfill reversibility not checked by A. |
| 16 Frontend quality | Out of A critical-service scope; no frontend files reviewed. |
| 17 Integration coherence | Sender calls safety gate; live readiness was found by Semble as another gate callsite but not line-audited. Findings F-001/F-004/F-008 cover coherence gaps. |
| 18 Documentation freshness | `docs/modules/account-safety-pipeline.md` matches the GGR formula and documents `history` as stubbed. It does not make the missing behavior-aware sender obvious enough for live-send rollout; see F-008. |

## Audit Gaps

- No live TDLib, production DB, production Redis, dependency install, or migration replay was run.
- No mutation testing or coverage threshold report was run.
- Sender targeted pytest command did not return before checkpoint; do not treat sender tests as passing from this sub-agent.
- This file intentionally avoids editing any code/tests/config/migrations or other audit docs.
