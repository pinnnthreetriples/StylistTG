# Test Strategy

Testing levels, scope, tooling, and run cadence for StylistTG.

## Testing Layers

| Layer | Scope | Tool | Run | Marker |
|---|---|---|---|---|
| Unit | Pure business logic, validators, redaction, phone hints | pytest / vitest | PR | `unit` |
| Service | DB + services, no HTTP layer | pytest + SQLite | PR | — |
| API | FastAPI endpoints, auth, roles, workspace scoping | pytest + TestClient | PR | `api` |
| Security | Auth/role matrix, workspace isolation, PII, secrets | pytest + TestClient | PR | `security` |
| Contract | OpenAPI drift, API-client wrapper correctness | npm check:api / vitest | PR | `contract` |
| Integration | PostgreSQL, Redis, RQ, storage | pytest markers | PR / nightly | `postgres`, `redis`, `integration` |
| Browser smoke | Critical UI flows | Playwright | PR | — |
| Live/manual | TDLib, Telegram, S3, staging | pytest live / manual | manual / nightly | `live` |

## What Each Level Covers

- **Unit** — `secret_redaction`, `phone_hints`, `import_validation`, `plan`, `step_policy`, config validators, storage key normalization. No DB, no HTTP, no external services.
- **Service** — `auth_batches`, `accounts`, `jobs`, `assets`, `dashboard`, `story_drafts`, `tenant_scope`. Uses in-memory SQLite via `db_session` fixture.
- **API** — Endpoint request/response contracts, status codes, error shapes, pagination, auth dependency presence. Uses `TestClient` with overridden session.
- **Security** — Role/auth matrix (no-auth/viewer/operator/admin), cross-workspace isolation, PII visibility per role, secret redaction in logs and errors.
- **Contract** — `npm run check:api` verifies OpenAPI spec matches live backend export. Vitest tests verify `@stylisttg/api-client` wrapper behavior with mocked fetch.
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

# OpenAPI drift check
npm run check:api

# Browser QA
npm run qa:browser
```

## When to Run

| Trigger | What runs |
|---|---|
| Every PR | backend lint, pytest (non-live), alembic upgrade, migration smoke, compileall, frontend lint/test/typecheck/build, browser QA, OpenAPI drift |
| Nightly | Full backend tests with coverage, full frontend suite, full Playwright, dependency audit |
| Manual | Live TDLib/Telegram tests (requires explicit secrets and feature flags) |

## Tests That Must Not Run in Normal PR

- `pytest -m live` — requires real TDLib library, Telegram credentials, external network
- Any test that calls `Telegram API`, `S3`, or external HTTP endpoints
- Tests gated behind `TDLIB_LIVE_ENABLED`, `STORIES_TDLIB_LIVE_ENABLED`, etc.
