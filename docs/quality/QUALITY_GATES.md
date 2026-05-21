# Quality Gates

Mandatory and optional checks before merging StylistTG PRs.

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
pytest tests \
  -n "$PYTEST_WORKERS" --dist="$PYTEST_DIST" \
  -m "not contract and not live and not integration and not slow" \
  --cov=app --cov=tools --cov-branch --cov-context=test
```

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
