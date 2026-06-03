# Quality Gates

Mandatory and optional checks before merging StylistTG PRs.

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
