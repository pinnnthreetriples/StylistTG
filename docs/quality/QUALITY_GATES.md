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
frontend build            npm run build
browser smoke             npm run qa:browser  # only when dashboard/browser paths change
Docker build              docker build -f backend/Dockerfile -t stylisttg-backend:test .
Semgrep                   semgrep scan --config p/ci --config .semgrep/stylisttg.yml --error backend/app apps packages
jscpd app                 npx jscpd app --threshold 2 --reporters json --output reports/jscpd-app
jscpd tests               npx jscpd tests --threshold 5 --reporters json --output reports/jscpd-tests
```

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
