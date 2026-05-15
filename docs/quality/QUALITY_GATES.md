# Quality Gates

Mandatory checks before merging any PR.

## Standard PR Gates

All PRs must pass:

```
backend lint              python -m ruff check .
backend format            python -m ruff format --check .
backend tests+coverage    python -m pytest tests -n auto --dist=loadscope --cov=app --cov=tools --cov-branch --cov-context=test
coverage gate             python scripts/coverage_gate.py
test quality analyzer     python -m tools.test_analyzer --path tests --coverage reports/coverage.json --severity INFO
backend pyright           python -m pyright app/api app/services app/schemas.py app/config.py app/workers
backend pip-audit         python -m pip_audit --skip-editable --progress-spinner=off
Alembic upgrade           python -m alembic upgrade head
migration smoke           python -m app.tools.migration_smoke
compileall                python -m compileall app
OpenAPI drift check       npm run check:api
frontend lint             npm run lint
frontend tests            npm test
frontend coverage         npm run coverage
frontend build            npm run build
browser smoke             npm run qa:browser  # only when dashboard/browser paths change
Docker build              docker build -f backend/Dockerfile -t stylisttg-backend:test .
Semgrep                   semgrep scan --config p/ci --config .semgrep/stylisttg.yml --error backend/app apps packages
Gitleaks PR diff          gitleaks git --config .gitleaks.toml --redact --log-opts="<base>..<head>" .
Trivy filesystem          trivy fs --scanners vuln,misconfig --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 .
Trivy backend image       trivy image --scanners vuln,misconfig --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 stylisttg-backend:test
complexity (soft)         python -m xenon --max-absolute B --max-modules A --max-average A app tools scripts
jscpd app                 npx jscpd app --threshold 2 --reporters json --output reports/jscpd-app
jscpd tests               npx jscpd tests --threshold 5 --reporters json --output reports/jscpd-tests
```

## Current CI Checks

Hard gates:

- `CI / Backend (Python 3.12)` - migrations, Ruff, pip-audit, Pyright subset, pytest coverage, compileall, backend Docker build.
- `CI / Frontend` - npm audit, OpenAPI drift, lint, tests, Vitest coverage, build.
- `Semgrep / Semgrep CE` - Semgrep with SARIF upload for PR annotations/code scanning.
- `Secrets Scan / Gitleaks PR diff` - scans the PR or push commit range and fails on detected secrets.
- `Trivy / Trivy filesystem` - repository filesystem dependency/config scan; fails on fixable HIGH/CRITICAL.
- `Trivy / Trivy backend image` - backend image scan; fails on fixable HIGH/CRITICAL.

Soft gates:

- `Complexity / Xenon complexity (soft)` - reports complexity for `backend/app`, `backend/tools`, and `backend/scripts`; does not block merges yet.
- `Test Quality / Pyright (strict, soft)` and `Schemathesis OpenAPI fuzz (soft)` - visible backlog checks.

Current required status checks for `main`:

- `Backend (Python 3.12)`
- `Frontend`
- `Browser QA`

Recommended required status checks after the quality/security expansion:

- `Backend (Python 3.12)`
- `Frontend`
- `Browser QA`
- `Test Quality / test-quality-pr`
- `Semgrep / Semgrep CE`
- `Secrets Scan / Gitleaks PR diff`
- `Trivy / Trivy filesystem`
- `Trivy / Trivy backend image`

Keep `Complexity / Xenon complexity (soft)` non-required until its threshold is promoted
from reporting-only to a hard gate.

Trivy uses `ignore-unfixed` so these hard gates block actionable HIGH/CRITICAL fixes
without failing permanently on upstream base-image advisories that have no patched
package yet. No `.trivyignore` entries are configured; add one only for a confirmed
false positive with an inline reason and expiry/issue reference.

Bugfix PRs must include a regression test that fails before the fix and passes after.

## Sensitive Area Gates

PRs touching the following areas require **additional** checks beyond the standard gates:

### Auth / Roles

- Security endpoint matrix tests pass (`pytest -m security`)
- No new endpoint without `require_authenticated` or `require_mutation_permission`
- Role escalation tested (viewer cannot mutate, operator cannot access admin endpoints)

### Workspace Isolation

- Cross-workspace negative tests pass
- No global lookup without `workspace_id` filter in new queries
- 404 returned (not 403) for foreign workspace objects to avoid existence leaks

### PII / Secrets

- PII regression tests pass (viewer sees `phone_hint`, not full `phone_number`)
- Secret redaction tests pass
- No raw secrets in log statements, error responses, or Sentry events
- Response schemas reviewed if changed

### Jobs / Workers

- Idempotency tests pass
- Lock acquisition tests pass
- Worker does not bypass tenant boundaries
- Job state machine transitions tested

### Storage / Uploads

- Path traversal property tests pass
- Upload size limits enforced
- Storage key normalization tested
- No absolute or `..` keys accepted

### Migrations

- `alembic upgrade head` succeeds from clean DB
- `migration_smoke` passes
- No data-destructive migration without explicit review

### Frontend API Contract

- `npm run check:api` passes (OpenAPI drift)
- API-client wrapper tests pass
- Response type changes reflected in generated schema

### Production Config

- Config validation tests pass
- Cloud/prod settings reject unsafe defaults (local auth, wildcard CORS, missing tokens)
- S3 storage requires all credentials
