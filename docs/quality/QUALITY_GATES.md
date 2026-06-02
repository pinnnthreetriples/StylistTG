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

Inline analyzer suppressions are allowed only when an exact assertion is
impossible (e.g. unstable third-party field, intentionally generic match) and
must include `reason="…"`. Suppressions tied to deferred work must reference
a tracking issue. The analyzer flags missing `reason=` as META001.

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
