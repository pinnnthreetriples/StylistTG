# Quality Gates

Mandatory and optional checks before merging StylistTG PRs.

## Test profile model

The canonical pytest marker expressions for each profile are exposed by
`backend/scripts/pytest_profiles.py`. GitHub Actions and `scripts/check.py`
resolve them at runtime so workflows, local commands, and docs cannot drift.

| Profile | Markers | When it runs | Hard-fail? |
|---|---|---|---|
| `pr` | `not contract and not live and not integration and not postgres and not redis and not slow and not benchmark and not mutation and not property_heavy and not nightly` | PR `backend-tests` job | Yes |
| `contract-security` | `contract and contract_security` | PR `contract-security` job + nightly | Yes |
| `nightly-slow-property` | `slow or property_heavy or nightly` | Scheduled `Nightly Backend Quality` | Yes |
| `nightly-contract` | `contract` | Scheduled fuzz job (`SCHEMATHESIS_MAX_EXAMPLES=100`) | Yes |
| `nightly-postgres-redis` | `postgres or redis or integration` | Scheduled service-container job | Yes |
| `nightly-mutation` | (driven by `scripts/mutation_suite.py`) | Scheduled mutation job | Yes (no `--soft`) |
| `benchmark` | `benchmark` | Manual `Pytest Benchmark` workflow only | N/A |
| `live` | `live` | Operator-only, manual | N/A |

Resolve a marker expression from the shell:

```bash
uv run python -m scripts.pytest_profiles pr-markers
uv run python -m scripts.pytest_profiles nightly-slow-property-markers
```

### Property test split

`@pytest.mark.property` is no longer used. Fast Hypothesis tests stay
inline with their feature/unit marker (no extra marker needed); calibration
and statistical property tests carry `@pytest.mark.property_heavy` and run
only in the nightly profile via `--run-property`.

### PR runtime budget

`backend/scripts/enforce_slow_test_budget.py` reads `reports/slow-tests.json`
and fails the PR `backend-tests` job if any **unmarked** test exceeds the
call/setup budget (`--max-call-seconds 3 --max-setup-seconds 2` by default).
Tests carrying any of `slow`, `integration`, `postgres`, `redis`,
`benchmark`, `property_heavy`, `nightly`, or `live` are exempt.

## Mutation testing policy

Mutation testing runs nightly only (the `mutation-selected` job in
`Nightly Backend Quality`) and **hard-fails** on survived non-equivalent
mutants — the `continue-on-error: true` carve-out and `--soft` argument
were both removed in #262.

Genuinely equivalent mutants can be allowlisted via
`backend/scripts/mutation_allowlist.json`. Every entry requires:

- `module` — file path of the mutated module;
- `mutant_signature` — the mutmut signature, e.g.
  `secret_redaction.py:42:replace_=_with_!=`;
- `reason` — non-empty explanation;
- `owner` — `@GitHubHandle`;
- `follow_up_issue` — `#NN` tracking ticket;
- `expires_at` — ISO date; after expiry the loader treats the entry
  as invalid so the gate fires again.

`backend/scripts/mutation_allowlist.py::load_allowlist` parses the JSON
and `active_entries(today=...)` returns only the non-expired set.
Behaviour is pinned by
`backend/tests/scripts/test_mutation_allowlist.py` (8 regression tests:
well-formed, every field validation, expiry filter, shipped-default
loads cleanly). The default registry ships empty.

Staged thresholds and mutmut target-list expansion are tracked in
follow-ups; this slice ships the policy + loader so allowlist entries
have a schema as soon as the first equivalent-mutant arises.

## Determinism policy

PR-selected tests must be deterministic. Forbidden patterns:

- `datetime.now()` / `time.time()` without a frozen clock — use
  `tests.helpers.determinism.frozen_clock` or `freezegun.freeze_time`.
- `random.random()` / `random.choice(...)` / similar without a seed —
  use `tests.helpers.determinism.seeded_rng()`.
- `requests.get(...)` / `httpx.get(...)` against real hosts — use the
  FastAPI `TestClient` or a `respx` / `responses` mock.
- File writes outside `tmp_path` / `tmp_path_factory`.
- Background tasks without an explicit fake worker / `freeze_time`.

The analyzer rules in `tools.test_analyzer.rules.flaky` catch the most
common violations (`TimeSleep`, `RandomWithoutSeed`, `DatetimeNow`,
`ExternalHTTPWithoutMarker`, `FilesystemWriteOutsideTmp`). New tests
should reach for the helpers in `tests/helpers/determinism.py` rather
than re-rolling local frozen-clock or seed primitives — the helpers are
pinned by `tests/helpers/test_determinism.py`.

## Analyzer rule coverage

The test analyzer (`tools.test_analyzer`) catches weak/flaky test
patterns before review. Most rules are AST-based and parse the Python
file's syntax tree, which avoids false positives from comments or
docstring mentions of the same patterns.

Coverage classes:

- **Assertions** — zero-assertion tests, `assert True`, self-equality,
  too-many-asserts, `pytest.raises` without `match=`, manual try/except,
  bare `assert response.json()` truthiness (TQA050), `assert "key" in
  response.json()` membership-only (TQA051).
- **Flaky** — uncontrolled clock, RNG without seed, network without
  marker, filesystem writes outside `tmp_path`.
- **Mocks** — mocks created without verifying calls, patch.start without
  stop, monkeypatch ordering.
- **Project (StylistTG)** — dependency-overrides without finally,
  TestClient without `app_client`, 4xx without typed error body
  (STG003), live tests without env guard.

Adding a new rule: subclass `Rule`, implement `check`, add a bad/good
sample pair to `backend/tests/tools/test_test_analyzer.py` (or a
dedicated test file), and register the instance in
`backend/tools/test_analyzer/rules/__init__.py::ALL_RULES`.

## RBAC endpoint matrix coverage

Every mutating `/api/` or `/diagnostics/` route (POST / PATCH / PUT /
DELETE) must appear in
`backend/tests/security/test_security_endpoint_matrix.ENDPOINT_MATRIX`.
The completeness gate
`backend/tests/security/test_endpoint_matrix_completeness.py` walks the
FastAPI route table on every PR and fails if a new mutating route is
missing.

The 53 pre-existing matrix gaps when this gate landed are pinned in
`backend/tests/security/rbac_matrix_baseline.json` (the ratchet
baseline). The baseline is **read-only**: entries can be removed when
the matrix grows, but additions are forbidden — new routes must land
in `ENDPOINT_MATRIX` directly. `test_baseline_does_not_grow` enforces
the rule and also flags baseline entries that no longer exist in the
app.

The companion analyzer rule `STG008 RBACRouteNotInMatrix` stays
disabled in `backend/test-quality.toml`: the pytest gate is
authoritative. The rule body is now a real heuristic stub instead of
the no-op placeholder it carried before, so future PRs can enable it
for soft pre-review hints without re-implementing it.

## Contract-security policy

The PR `contract-security` profile runs the narrow hard subset of
`tests/contract/security/`, which protects auth, operator-token,
workspace/object authorization, diagnostics, metrics, and asset
contracts. Broad OpenAPI fuzz lives in the nightly `nightly-contract`
profile and uses `SCHEMATHESIS_MAX_EXAMPLES=100`.

Every intentional exclusion from the contract-security profile must
live in `backend/tests/contract/security/exclusions.py` and provide:

- a precise path pattern + HTTP method;
- a `reason` for the exclusion;
- an `@owner` GitHub handle;
- a `#follow_up_issue` link;
- an `expires_at` ISO date (`YYYY-MM-DD`). Past expiry fails the gate;
  recommended cap is `MAX_EXCLUSION_DAYS` (90 days) — longer requires a
  renewed justification.

`test_exclusions_policy.py` enforces the schema and the non-expired
contract. The registry is empty by default — adding an entry requires
a passing regression test.

## Coverage policy

Backend coverage is **branch-first**: every required pytest run uses
`--cov-branch`, and `scripts/coverage_gate.py` aborts with exit 2 if the
generated `coverage.json` was not produced with branch coverage enabled.
Missing branch data is never silently treated as 100% — the gate forces
the pipeline to be fixed at source.

Three layers of enforcement:

1. **Per-package** thresholds (`THRESHOLDS`) anchor each backend
   directory at its current measured floor. Lowering a threshold
   requires explicit reviewer approval and an inline comment.
2. **Critical file** thresholds (`CRITICAL_FILE_THRESHOLDS`) prevent
   small high-risk files from being hidden by their package average.
   The gate fails if a critical file is missing from the report at all.
3. **Coverage ratchet** — thresholds are anchored at measured floors;
   any regression breaks the build, any improvement should be reflected
   by raising the threshold in the same PR.

The gate's behavior is pinned by `backend/tests/scripts/test_coverage_gate_branch_validation.py`
(10 regression tests covering missing report, missing meta block, branch
coverage disabled, critical file absence, and threshold math).

## DB fixture strategy

The default `db_session` fixture in `backend/tests/conftest.py` builds a
fresh in-memory SQLite engine **and** the full schema for every test. It
gives maximum isolation at the cost of repeated `Base.metadata.create_all`
work.

For DB-heavy tests that do not commit at the test layer, the opt-in
`transactional_db_session` fixture in `backend/tests/helpers/db_fixtures.py`
keeps the engine and schema across the whole pytest session and wraps
each test in a SAVEPOINT-backed transaction that rolls back at teardown.
Tests migrate by renaming `db_session` → `transactional_db_session`.

The fixture's isolation contract is pinned by
`backend/tests/helpers/test_db_fixtures.py`. Tests that need real commits
visible from a separate engine (e.g. cross-process or multi-connection
scenarios) must stay on the per-engine `db_session` fixture.

## Strict assertion policy

Backend tests must assert the behaviour that matters, not just that an
endpoint returned some status code. Status-only API tests, "detail in body"
checks, `assert result is not None`, `assert mock.called`, and manual
`try/except` capture patterns are prohibited in security/auth/API/storage
tests.

### Required patterns

- **Exact error envelope.** Every 4xx/5xx test asserts the exact body shape,
  including `error_code`/`detail`. Use `tests.helpers.assertions.assert_error_response`.
- **Side-effect safety.** Every failure-path test asserts that no rows were
  written and no queue mock was called. Use `assert_no_jobs_created` and
  `assert_queue_not_called` helpers.
- **Workspace isolation.** Workspace-scoped tests cover both own- and
  foreign-workspace paths. Foreign probes must return 404 and must not leak
  the foreign id; use `assert_foreign_workspace_denied`.
- **Exceptions.** Unit/security/domain tests use `pytest.raises(..., match=...)`
  with an exact exception type assertion. Manual `try/except` capture
  patterns are forbidden — they hide which branch executed.
- **Datetime.** Response timestamps go through `assert_rfc3339_aware`, not
  `endswith("Z") or "+" in value`.
- **Mocks.** `assert_called_once_with(...)` / `assert_exact_calls(...)` /
  `assert_not_called()`, never `assert mock.called` / `mock.call_count > 0`.

### Suppression policy

Inline analyzer suppressions use a three-field format and are validated by
`tools.test_analyzer`:

```python
# test-analyzer: disable=TQA050 reason="…" issue="#263" expires="2026-08-31"
```

- `reason="…"` — required. Missing → **META001** WARNING.
- `issue="#NNN"` — recommended for deferred work, optional for permanent
  false-positive carve-outs. The format is `#` followed by digits.
- `expires="YYYY-MM-DD"` — recommended for deferred work. Past expiry
  fires **META003** CRITICAL — the analyzer hard-fails CI when an
  expiring suppression has lapsed. The field regex is permissive
  (any quoted value), so unparseable values like
  `expires="not-a-date"` / `expires="2026-99-99"` ALSO fire META003
  instead of being silently dropped — a typo cannot turn a suppression
  into an immortal one.

Permanent suppressions (analyzer false positives on patterns that are
already strict, e.g. exception-attribute checks the rule does not yet
understand) may omit `issue=`/`expires=`. They MUST still include a
`reason=` that names the false-positive and identifies the underlying
rule limitation, so a future analyzer improvement can clean them up.

The same three-field format also applies to `disable-file=`.

Helpers live in `backend/tests/helpers/assertions.py`; their behaviour is
pinned by `backend/tests/helpers/test_assertions.py`.

## Zero-warning / zero-soft-fail policy

The backend test-quality gate is strict: any pytest warning, unknown marker,
malformed pytest config, unexpected xfail-pass, test-analyzer finding,
soft-failed quality check, or unimplemented enabled analyzer rule fails CI
immediately. Long-running checks may stay in nightly workflows, but they must
still be hard failures when they run.

### Pytest

- `strict_config = true`, `strict_markers = true`, `xfail_strict = true` and
  `filterwarnings = ["error"]` are required in `backend/pyproject.toml`.
- Every `@pytest.mark.X` or module-level `pytestmark` must be registered in
  `[tool.pytest.ini_options].markers`. A regression test
  (`tests/tools/test_strict_enforcement_262.py`) pins this.
- Warning ignores are narrow regex-based entries with a `Why:` line and a
  tracking issue. Do not add broad `ignore::DeprecationWarning` /
  `ignore::UserWarning` entries.

### Test analyzer

- Run with `--severity INFO --fail-on-severity INFO` in CI. Any INFO/WARNING/
  CRITICAL finding fails the run.
- Enabled rules in `backend/test-quality.toml [project_rules]` must have real
  detection logic. No-op placeholders must be disabled with a TODO and a
  linked follow-up issue (e.g. STG008 is disabled pending #269).

### CI workflows

- Quality jobs do not use `continue-on-error: true` on the test-quality path.
  Carve-outs are allowed only when the step is explicitly documented as
  `non-blocking` in a preceding comment (e.g. the transitional Bandit step in
  the `audit` job, tracked separately for hard-gate promotion).
- Nightly quality jobs hard-fail. A check being slow is not a reason to ignore
  its result; expensive checks belong in nightly but must still block.

### Local gate (`backend/scripts/check.py`)

- Mutation runs hard. The `--soft` flag was removed.
- Any remaining `soft=True` Check entry must reference a tracking issue in an
  inline comment.



## Required PR path

The required aggregator is:

`Test Quality / test-quality-pr`

It requires these jobs to pass:

- `lint-format`: ruff check, ruff format check, and test requirement gate for new backend production files.
- `typecheck`: scoped Pyright check and full strict Pyright report.
- `backend-tests`: pytest PR profile, coverage JSON/XML, branch coverage, package coverage gate, full-suite and changed-tests analyzer SARIF/JSON, slow-test report, fixture audit, and runtime telemetry summary.
- `audit`: pip-audit over the broad quality toolchain extras.
- `duplication`: jscpd JSON reports for backend app and tests.
- `contract-security`: narrow hard contract subset for security-sensitive API contract regressions.

CI installs narrow backend dependency extras per job, except `audit`, which intentionally installs the broad quality extra set so `pip-audit` does not lose coverage compared with the previous `dev` environment. Local developer setup keeps using the `dev` extra for the full quality toolchain.

## Backend PR pytest profile

Required PR command shape:

```bash
PYTEST_PROFILE=pr
uv sync --locked --extra test
pytest tests \
  --ignore=tests/contract \
  -n "$PYTEST_WORKERS" --dist="$PYTEST_DIST" \
  -m "not contract and not live and not integration and not slow" \
  --cov=app --cov=tools --cov-branch --cov-context=test
```

The PR test profile installs the `test` extra only. It must ignore
`tests/contract` at collection time because contract modules import
Schemathesis from the separate `contract` extra before marker deselection.

Current required PR mode:

```text
PYTEST_WORKERS=2
PYTEST_DIST=worksteal
```

`pyproject.toml` does not define the PR marker expression globally. Required, nightly, benchmark, integration, and live workflows must pass their marker profiles explicitly.

## Optional/non-required checks

| Check | Workflow | Purpose |
|---|---|---|
| Contract fuzz soft PR signal | `Test Quality / contract-fuzz` | Broad OpenAPI/Schemathesis drift visibility without blocking required path |
| Trivy tdlib image | `Trivy / Trivy tdlib image` | TDLib image CRITICAL vulnerability gate; recommended required after first green run |
| Pytest Benchmark | `Pytest Benchmark` | Manual xdist runtime comparison before changing PR runtime |
| Nightly Backend Quality | `Nightly Backend Quality` | slow/property/contract/postgres/mutation checks |
| Complexity | existing soft workflow | complexity debt visibility |

## Artifact policy

PR jobs should upload only machine-readable lightweight artifacts:

- `coverage.json`
- `coverage.xml`
- `test-quality.sarif`
- `test-quality.json`
- `changed-tests/test-quality.sarif`
- `changed-tests/test-quality.json`
- `slow-tests.json`
- `fixture-audit.json`
- `pytest-runtime-summary.txt`
- `jscpd-report.json`

Do not upload HTML coverage/jscpd reports in every PR. Generate heavy HTML only in nightly/manual workflows.

## Runtime telemetry policy

`pytest-runtime-summary.txt` is the first place to check after any suite or CI change. It should include `pytest_total_seconds`, `slow_report_seconds`, `fixture_audit_seconds`, `coverage_gate_seconds`, `test_analyzer_seconds`, and `changed_test_analyzer_seconds`.

Use this file to decide whether the next optimization belongs in pytest collection/execution, coverage, analyzer, fixture audit, or artifact handling.

## Promotion rules

- Do not reduce coverage thresholds for speed.
- Do not disable branch coverage.
- Do not remove tests to improve runtime.
- Promote `slow-tests.json` to a hard gate only after baseline is stable.
- Promote benchmark-selected xdist mode only after the benchmark matrix shows a clear repeated win.
- Keep live, integration, and mutation checks outside the required PR path.

## Sensitive area gates

PRs touching auth, workspace isolation, PII, jobs/workers, storage, migrations, frontend API contracts, or production config require targeted regression tests in addition to the standard gates.
