# Test Strategy

Testing levels, scope, tooling, and run cadence for StylistTG.

## Testing Layers

| Layer | Scope | Tool | Run | Marker |
|---|---|---|---|---|
| Unit | Pure business logic, validators, redaction, phone hints | pytest / vitest | PR | `unit` |
| Service | DB + services, no HTTP layer | pytest + SQLite | PR | — |
| API | FastAPI endpoints, auth, roles, workspace scoping | pytest + TestClient | PR | `api` |
| Security | Auth/role matrix, workspace isolation, PII, secrets | pytest + TestClient | PR | `security` |
| Contract | OpenAPI drift, API-client wrapper correctness, deeper OpenAPI fuzz | npm check:api / vitest / Schemathesis | PR / nightly | `contract` |
| Integration | PostgreSQL, Redis, RQ, storage | pytest markers | PR / nightly | `postgres`, `redis`, `integration` |
| Browser smoke | Critical UI flows | Playwright | PR | — |
| Live/manual | TDLib, Telegram, S3, staging | pytest live / manual | manual only | `live` |

## What Each Level Covers

- **Unit** — `secret_redaction`, `phone_hints`, `import_validation`, `plan`, `step_policy`, config validators, storage key normalization. No DB, no HTTP, no external services.
- **Service** — `auth_batches`, `accounts`, `jobs`, `assets`, `dashboard`, `story_drafts`, `tenant_scope`. Uses in-memory SQLite via `db_session` fixture.
- **API** — Endpoint request/response contracts, status codes, error shapes, pagination, auth dependency presence. Uses `TestClient` with overridden session.
- **Security** — Role/auth matrix (no-auth/viewer/operator/admin), cross-workspace isolation, PII visibility per role, secret redaction in logs and errors.
- **Contract** — `npm run check:api` verifies OpenAPI spec matches live backend export. Vitest tests verify `@stylisttg/api-client` wrapper behavior with mocked fetch. PR CI keeps Schemathesis soft and shallow; the nightly reliability workflow increases Schemathesis examples and stores reports for triage.
- **Integration** — Tests that require real PostgreSQL or Redis (marked `postgres`/`redis`). Run in CI with service containers.
- **Browser smoke** — Playwright tests against the built frontend. Verifies critical flows render and interact correctly.
- **Live** — TDLib / Telegram API calls against real infrastructure. **Never run in normal PR CI.**

## Commands

### Backend

```bash
cd backend

# All tests (fast, SQLite)
python -m pytest

# By marker
python -m pytest -m unit
python -m pytest -m api
python -m pytest -m security
python -m pytest -m "not live"

# With coverage
python -m pytest --cov=app --cov-report=term-missing

# Parallel (requires pytest-xdist)
python -m pytest -n auto

# Nightly-style reliability profiles
python scripts/check.py --only nightly-randomized
python scripts/check.py --only mutation

# Single test
python -m pytest tests/test_auth_service.py::test_name -q

# Lint
python -m ruff check .
```

### Frontend

```bash
# All workspace tests
npm test

# API-client only
npm --workspace @stylisttg/api-client test

# Lint + typecheck + build
npm run lint
npm run typecheck
npm run build
npm run coverage

# OpenAPI drift check
npm run check:api

# Browser QA
npm run qa:browser
```

## When to Run

| Trigger | What runs |
|---|---|
| Every PR | backend lint/format, pytest coverage (non-live), coverage gate, test analyzer, Pyright, pip-audit, alembic upgrade, migration smoke, compileall, backend Docker build, frontend npm audit/OpenAPI drift/lint/test/coverage/build, Semgrep, Gitleaks, Trivy |
| Soft PR signal | Xenon complexity report for backend `app`, `tools`, and `scripts` |
| Path-filtered PR | Browser QA for dashboard/browser-related changes |
| Nightly/manual reliability workflow | randomized backend tests across fixed seeds, flaky rerun detection, scoped mutation testing, deeper Schemathesis fuzz, jscpd HTML/JSON reports |
| Manual live validation | Live TDLib/Telegram/S3 tests (requires explicit secrets, feature flags, and operator approval) |

## Nightly Reliability Suite

`.github/workflows/nightly-test-reliability.yml` is scheduled nightly and can be run with `workflow_dispatch`. It is intentionally not a PR trigger, so normal PR gates stay fast.

Hard:

- Backend randomized reliability runs `pytest-randomly` with seeds `101`, `202`, and `303`; any failing seed fails the job. JUnit files and `reports/randomized-summary.json` are uploaded.

Soft/reporting:

- Flaky detection runs pytest with `pytest-rerunfailures`, writes `reports/flaky-report.json`, and warns when a test passes only after rerun.
- Mutation testing uses `mutmut` against the scoped pure modules in `pyproject.toml`, writes `reports/mutation-report.json`, and reports killed/survived/timeout/incompetent mutants without blocking the first PR.
- Contract fuzz runs the existing Schemathesis test with a higher nightly `SCHEMATHESIS_MAX_EXAMPLES` value and a step timeout.
- jscpd emits HTML/JSON reports for backend app, backend tests, and frontend `apps`/`packages` without changing the ordinary thresholds.

Promote a soft nightly check to hard only after its baseline is clean for several consecutive nightly runs, the owning team has triaged remaining candidates, and the expected runtime is stable enough not to create noisy failures.

## Tests That Must Not Run in Normal PR

- `pytest -m live` — requires real TDLib library, Telegram credentials, external network
- Any test that calls `Telegram API`, `S3`, or external HTTP endpoints
- Tests gated behind `TDLIB_LIVE_ENABLED`, `STORIES_TDLIB_LIVE_ENABLED`, etc.
- Nightly randomized/flaky jobs also set live/storage env vars to safe local values and run `-m "not live and not contract"`; Schemathesis runs in its own soft contract fuzz job.
