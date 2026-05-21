# Quality Gates

Mandatory and optional checks before merging StylistTG PRs.

## Required PR path

The required aggregator is:

```text
Test Quality / test-quality-pr
```

It requires these jobs to pass:

```text
lint-format
  ruff check
  ruff format --check
  require tests for new backend/app files

typecheck
  pyright scoped backend surface
  pyright full strict report

backend-tests
  pytest PR profile
  coverage.py JSON/XML
  branch coverage
  package coverage gate
  one-pass test analyzer SARIF+JSON
  slow-test report artifact
  fixture audit artifact

audit
  pip-audit

duplication
  jscpd backend/app JSON
  jscpd backend/tests JSON
```

## Backend PR pytest profile

```bash
PYTEST_PROFILE=pr
pytest tests \
  -n "$PYTEST_WORKERS" --dist="$PYTEST_DIST" \
  -m "not contract and not live and not integration and not slow" \
  --cov=app --cov=tools --cov-branch --cov-context=test
```

Current default until benchmark proves otherwise:

```text
PYTEST_WORKERS=auto
PYTEST_DIST=loadscope
```

## Optional/non-required checks

| Check | Workflow | Purpose |
|---|---|---|
| Contract fuzz soft PR signal | `Test Quality / contract-fuzz` | OpenAPI/Schemathesis drift visibility without blocking required path |
| Pytest Benchmark | `Pytest Benchmark` | Compare xdist runtime modes before changing PR runtime |
| Nightly Backend Quality | `Nightly Backend Quality` | slow/property/contract/postgres/mutation checks |
| Complexity | existing soft workflow | complexity debt visibility |

## Artifact policy

PR jobs should upload only machine-readable lightweight artifacts:

```text
coverage.json
coverage.xml
test-quality.sarif
test-quality.json
slow-tests.json
fixture-audit.json
jscpd-report.json
```

Do not upload HTML coverage/jscpd reports in every PR. Generate heavy HTML only in nightly/manual workflows.

## Promotion rules

- Do not reduce coverage thresholds for speed.
- Do not disable branch coverage.
- Do not remove tests to improve runtime.
- Promote `slow-tests.json` to a hard gate only after baseline is stable.
- Promote benchmark-selected xdist mode only after the benchmark matrix shows a clear repeated win.
- Keep live, integration, and mutation checks outside the required PR path.

## Sensitive area gates

PRs touching auth, workspace isolation, PII, jobs/workers, storage, migrations, frontend API contracts, or production config require targeted regression tests in addition to the standard gates.
