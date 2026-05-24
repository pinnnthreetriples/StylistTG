# Quality, Tests, Logging, and Integration Findings

Task: [#148](https://github.com/pinnnthreetriples/StylistTG/issues/148) - Task 42, Full safety pipeline audit.

Agent: D - Quality, tests, logging, integration coherence.

Scope: dimensions 9 test coverage, 10 code quality, 12 logging quality, 17 integration coherence.

## Summary

- Findings: 3 total.
- Severity counts: P0 0, P1 1, P2 2, P3 0.
- Dimension counts: test coverage 2, code quality 1, logging quality 0, integration coherence 2.
- Files edited: this audit artifact only.
- Live operations: none. No TDLib, Telegram, production DB, production Redis, dependency install, migration, or production-like command used.

## Evidence Collected

- Read project instructions: `.mex/ROUTER.md`, `.mex/context/conventions.md`, `.mex/context/security.md`, `.mex/context/setup.md`, `.mex/context/workers.md`, `.mex/context/warmup.md`, and `.mex/patterns/documentation-audit.md`.
- Reviewed Phase 0 setup: `docs/audits/2026-05-safety-pipeline-audit/00-setup.md`.
- Semble code search over safety gate, tests, logging, metrics, contracts, and frontend use sites.
- Exact searches:
  - TODO/FIXME: `rtk rg -n "TODO|FIXME|XXX|HACK" backend/app backend/tests apps packages`.
  - Safety gate callsites/contracts: `rtk rg -n "evaluate_safety_gate|AccountSafetyGate\\(|safety-gate|SafetyGateVerdict|SafetyGateIntent|safety_gate" ...`.
  - Logging/print discipline: `rtk rg -n "print\\(|console\\.(log|warn|error)|traceback\\.print|pdb\\.set_trace" backend/app/services backend/app/modules backend/app/api backend/app/observability apps/dashboard/src packages/api-client/src`.
  - Contract/frontend coherence: `rtk rg -n "SafetyGateReason|fetchAccountSafetyGate|accountSafetyGateQueryOptions|SafetyGateBanner|editing|warmup|commenting" ...`.
- Tool checks:
  - `cd backend; python -m ruff check app/services/account_safety_gate.py app/services/safety_gate_reserve.py app/observability/safety_metrics.py app/services/neuro_commenting/live_readiness_service.py app/services/neuro_commenting/sender_service.py app/modules/warmup/dispatcher.py app/modules/account_editing/service.py tests/test_account_safety_gate.py tests/test_account_safety_gate_integration.py tests/integration/test_safety_pipeline_e2e.py` passed.
  - `cd backend; python -m tools.test_analyzer --path tests/test_account_safety_gate.py --severity INFO --format text` passed with no findings.
  - `cd backend; python -m tools.test_analyzer --path tests/test_account_safety_gate_integration.py --severity INFO --format text` passed with no findings.
  - `cd backend; python -m tools.test_analyzer --path tests/integration/test_safety_pipeline_e2e.py --severity INFO --format text` passed with no findings.
  - Full pytest collection was not re-run to completion because Phase 0 already found the `prometheus_client` blocker; a targeted collect against `tests/test_account_safety_gate.py tests/test_safety_metrics.py` produced no useful output within the checkpoint window.

## Findings

### F-041 Metrics tests hard-require optional `prometheus_client`

Severity: P1

Dimension: 9 test coverage

Affected:

- `backend/tests/test_account_safety_gate.py:6`
- `backend/tests/test_account_safety_gate.py:462`
- `backend/tests/test_safety_metrics.py:8`
- `backend/app/observability/safety_metrics.py:11`
- `backend/app/observability/safety_metrics.py:42`

Found by:

- Phase 0 setup audit.
- Exact import search for `prometheus_client`.
- Targeted pytest collection attempt during this audit.

Description:

Runtime metrics are designed as optional: `backend/app/observability/safety_metrics.py` catches `ImportError` and disables metrics when `prometheus_client` is absent. The tests do not follow that optional contract. `test_account_safety_gate.py` and `test_safety_metrics.py` import `CollectorRegistry` / `generate_latest` directly from `prometheus_client`, so an environment missing that optional package cannot even collect safety-gate tests.

Reproduction expected/actual:

- Expected: in an environment without `prometheus_client`, non-metrics safety-gate tests collect/run, while metrics-specific tests skip with a clear reason or the dependency is declared as required for the backend test env.
- Actual: Phase 0 recorded `pytest tests --ignore=tests/contract --ignore=tests/benchmarks --collect-only -q` failing after collecting 1770 tests because `prometheus_client` is missing.

Impact:

Safety pipeline regression coverage becomes brittle in clean or partial local environments. One optional observability dependency blocks collection of account safety gate tests, safety metrics tests, and potentially broad backend test runs.

Suggested fix:

Either make `prometheus_client` a required backend/test dependency, or gate metrics-specific tests with `pytest.importorskip("prometheus_client")` and split non-metrics safety-gate coverage away from direct Prometheus imports.

Effort: S

### F-042 E2E gate-call-count test is self-fulfilling

Severity: P2

Dimension: 9 test coverage, 17 integration coherence

Affected:

- `backend/tests/integration/test_safety_pipeline_e2e.py:477`
- Safety-gate integrations asserted elsewhere: `backend/services/neuro_commenting/live_readiness_service.py:271`, `backend/app/services/neuro_commenting/sender_service.py:891`, `backend/app/modules/warmup/dispatcher.py:443`, `backend/app/modules/account_editing/service.py:215`

Found by:

- Semble search for safety pipeline tests.
- Manual review of `test_pipeline_uses_account_safety_gate_at_least_five_times`.

Description:

`test_pipeline_uses_account_safety_gate_at_least_five_times` monkeypatches `AccountSafetyGate.evaluate`, then directly calls the local `_gate()` helper five times in a loop and asserts `len(calls) >= 5`. This proves the helper calls the gate, not that the safety pipeline uses the gate across live readiness, sender preflight, warmup dispatch, account editing, or API boundaries.

Reproduction expected/actual:

- Expected: if a real pipeline boundary drops its `evaluate_safety_gate` call, the integration test fails.
- Actual: this test still passes because it manufactures five direct `_gate()` calls inside the test body.

Impact:

The test name suggests cross-pipeline integration coverage, but the assertion cannot catch missing or bypassed gate calls in production workflows. That weakens confidence in the audit-critical "all paths go through safety gate" invariant.

Suggested fix:

Replace the call-count loop with workflow-driven assertions. For example, monkeypatch/count `evaluate_safety_gate`, run live readiness, sender preflight, warmup dispatch, account editing preview, and the API route, then assert the expected `(account_id, intent)` calls. Keep separate per-boundary tests for blocker behavior.

Effort: M

### F-043 Warmup isolation is implemented but not integrated into safety gate

Severity: P2

Dimension: 10 code quality, 17 integration coherence

Affected:

- `backend/app/services/account_safety_gate.py:411`
- `backend/app/modules/warmup/isolation.py:34`
- `backend/app/modules/warmup/commands.py:89`
- `backend/app/modules/warmup/router.py:209`
- `backend/tests/warmup/test_warmup_isolation.py:1`
- `backend/tests/api/test_warmup_sessions_api.py:106`

Found by:

- TODO/FIXME search.
- Exact search for warmup isolation service/tests.

Description:

`account_safety_gate._warmup_reasons` still contains the TODO "Warmup isolation conflict check will be wired when a dedicated conflict service exists." That service now exists under `app.modules.warmup.isolation`, has API/read-model surfaces, and has tests. The central safety gate still cannot surface an isolation conflict as a gate reason.

Reproduction expected/actual:

- Expected: with an active warmup isolation claim, the safety gate either reports a clear reason/code or the codebase documents and tests that isolation is enforced exclusively outside the gate.
- Actual: `_warmup_reasons` checks proxy and terminal state only, then returns without consulting the existing isolation claim service.

Impact:

The project has two safety concepts that look related but are not coherently connected: warmup isolation ownership and the canonical safety gate. Future callsites may assume the gate includes isolation because the TODO says it should, while existing isolation enforcement lives elsewhere.

Suggested fix:

Choose one boundary and make it explicit. Prefer wiring a small isolation check into `AccountSafetyGate` for relevant intents, with a reason code and integration test. If isolation must stay separate, replace the stale TODO with a documented invariant and add tests proving account mutation paths consult isolation independently.

Effort: M

## Explicit No-Issue Checks

- Logging quality: no `print()`, `console.log/warn/error`, `traceback.print*`, or `pdb.set_trace` findings in backend services/modules/API/observability or dashboard/API-client app code. Print usage found only in scripts/tools, which are CLI surfaces.
- Structured logging: safety-adjacent backend paths use `log_event`, `log_warn`, or `log_request`; `logging_utils` centralizes redaction before writing events/fields.
- Safety gate callsites: current production callsites exist in NeuroCommenting live readiness, NeuroCommenting sender preflight, warmup dispatcher, and account editing preview.
- Contract coherence: backend `SafetyGateVerdict`/`SafetyGateIntent` are exported through generated OpenAPI types; frontend `fetchAccountSafetyGate`, `accountSafetyGateQueryOptions`, and `SafetyGateBanner` consume those generated types rather than local string unions.
- Test analyzer: targeted safety-gate quality tests produced no `tools.test_analyzer` findings.
- Ruff: targeted safety-pipeline backend files and safety tests passed `python -m ruff check`.

## Open Verification Gaps

- Could not mark full pytest collection as clean because Phase 0's missing `prometheus_client` gap blocks/complicates collection.
- Did not run live TDLib/Telegram, production DB, production Redis, dependency installs, migrations, or broad frontend commands by scope.
