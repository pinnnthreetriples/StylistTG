# Developer Workflow

Local commands that reproduce the StylistTG backend quality gates 1:1
with the GitHub Actions pipeline. Run these before pushing so feedback
arrives in seconds, not in the cloud minutes later.

All commands assume `cd backend` unless stated otherwise.

## Bootstrap

```bash
# Install the test + contract + lint + typecheck extras (CI installs
# narrower sets per job; the dev extra below is the local superset).
uv sync --locked --extra dev
```

If you only need the PR profile:

```bash
uv sync --locked --extra test --extra contract --extra lint --extra typecheck
```

## Required PR checks (run in order)

```bash
# Lint + format.
uv run ruff check .
uv run ruff format --check .

# Typecheck (scoped, fast).
uv run pyright app/api app/services app/schemas.py app/config.py app/workers
uv run pyright              # full strict (slower; matches the typecheck CI job)

# Required PR pytest profile — canonical marker expression comes from
# scripts/pytest_profiles.py (#264) so local and CI never drift.
uv run pytest tests \
  --ignore=tests/contract \
  -m "$(uv run python -m scripts.pytest_profiles pr-markers)" \
  -n 2 --dist=worksteal \
  --cov=app --cov=tools --cov-branch --cov-context=test \
  --cov-report=json:reports/coverage.json \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=term-missing:skip-covered \
  --benchmark-disable \
  --durations=50 --durations-min=0.5 \
  -q 2>&1 | tee reports/pytest.log

# Coverage gate (per-package + critical-file branch coverage, #265).
uv run python scripts/coverage_gate.py

# Test-quality analyzer (#262 — hard-fail on INFO+).
uv run python -m tools.test_analyzer \
  --path tests \
  --coverage reports/coverage.json \
  --format sarif,json \
  --output-dir reports \
  --severity INFO \
  --fail-on-severity INFO

# Slow-test budget (#264). report_slow_tests.py parses the pytest log
# that was captured via `tee reports/pytest.log` above; --require-report
# matches the CI invocation so a missing log fails the budget gate.
uv run python scripts/report_slow_tests.py \
  --log reports/pytest.log \
  --output reports/slow-tests.json \
  --threshold 3
uv run python scripts/enforce_slow_test_budget.py \
  --report reports/slow-tests.json \
  --profile pr \
  --require-report

# Contract-security narrow subset (#266).
uv run pytest tests/contract/security \
  -m "$(uv run python -m scripts.pytest_profiles contract-security-markers)" \
  -p no:randomly \
  --tb=short -q
```

`scripts/check.py` chains the above. Use `--fast` to skip the slowest
checks (pyright, coverage gate, pip-audit, complexity); use `--only
<name>` to run a single check.

## Nightly profiles (manual reproduction)

```bash
# Slow + property_heavy + nightly markers (#264).
uv run pytest tests \
  --ignore=tests/contract \
  -m "$(uv run python -m scripts.pytest_profiles nightly-slow-property-markers)" \
  --run-property \
  --hypothesis-show-statistics \
  -p no:randomly --tb=short

# Schemathesis nightly fuzz.
SCHEMATHESIS_MAX_EXAMPLES=100 \
uv run pytest tests/contract -m contract -p no:randomly --tb=short -q

# Mutation testing (#267 — hard-fail, no --soft).
uv run python scripts/mutation_suite.py
```

## Troubleshooting

### "strict_markers requires every used marker to be registered"

A `@pytest.mark.X` decorator uses a name not in
`[tool.pytest.ini_options].markers` in `backend/pyproject.toml`. Add the
marker with a short docstring entry. The regression test
`tests/tools/test_strict_enforcement_262.py::test_pyproject_markers_cover_all_pytestmark_usages`
catches new violations.

### "FAILED tests/architecture/test_structure_audit_report*"

You added or moved a file under `backend/app/` or `backend/tests/` and
the committed architecture artifacts are now stale. Regenerate:

```bash
uv run python scripts/structure_audit.py
```

Commit the resulting changes to `docs/architecture/structure-audit.json`,
`architecture-debt-inventory.json`, and `STRUCTURE_AUDIT.md`.

### Analyzer fails at INFO severity

The analyzer (`tools.test_analyzer`) flagged a new finding at INFO+.
Either:

1. **Fix the underlying weakness** — usually a status-only API check,
   `assert mock.called`, `assert "X" in response.json()`, or a manual
   `try/except` capture pattern. Use the helpers in
   `tests/helpers/assertions.py` (#263).
2. **Suppress with `reason=` and a tracking issue** —
   `# test-analyzer: disable=<RULE_ID> reason="…"` on the line above
   the offence, or `disable-file=<RULE_ID>` near the top of the file
   for a wide carve-out. META001 fires if `reason=` is missing.

### Coverage gate fails on `branch_coverage`

You ran pytest without `--cov-branch`. The gate (#265) refuses to trust
branch percentages produced without it. Re-run with the canonical
`--cov-branch --cov-report=json:reports/coverage.json` flags.

### `enforce_slow_test_budget.py` flags an unmarked test

Either speed the test up (move expensive setup behind a session-scoped
fixture, mock the slow dependency) or mark it with `slow` / `integration`
/ `postgres` / `redis` / `benchmark` / `property_heavy` / `nightly` so
it moves to the nightly profile.

### Determinism analyzer findings

The analyzer flagged `datetime.now()`, `random.random()` without seed,
network call without marker, or filesystem write outside `tmp_path`.
Switch to the helpers in `tests/helpers/determinism.py` (#271):

```python
from tests.helpers.determinism import frozen_clock, seeded_rng

with frozen_clock():
    ...

rng = seeded_rng()
```

## Where each policy lives

| Concern | Source of truth |
|---|---|
| Strict pytest + warnings | `backend/pyproject.toml [tool.pytest.ini_options]` |
| Test-quality rule enable/disable | `backend/test-quality.toml` |
| Pytest profile marker expressions | `backend/scripts/pytest_profiles.py` |
| Coverage thresholds | `backend/scripts/coverage_gate.py` |
| Mutation allowlist schema | `backend/scripts/mutation_allowlist.py` |
| Branch-protection ruleset | `.github/branch-protection.main.json` |
| Quality gates policy | `docs/quality/QUALITY_GATES.md` |
| Required CI checks list | `docs/quality/REQUIRED_CHECKS.md` |

## Where each helper lives

| Helper | Location | Issue |
|---|---|---|
| Strict assertion helpers | `backend/tests/helpers/assertions.py` | #263 |
| Determinism (clock + RNG) | `backend/tests/helpers/determinism.py` | #271 |
| Opt-in transactional DB session | `backend/tests/helpers/db_fixtures.py` | #268 |
| Contract-security exclusions | `backend/tests/contract/security/exclusions.py` | #266 |
| RBAC matrix completeness gate | `backend/tests/security/test_endpoint_matrix_completeness.py` | #269 |
