# Test Strategy

Testing levels, suite profiles, tooling, and run cadence for StylistTG.

## Backend suite profiles

| Profile | Purpose | Command | Required |
|---|---|---|---|
| PR | Fast deterministic backend gate | `pytest tests -m "not contract and not live and not integration and not slow"` | yes, through `Test Quality / test-quality-pr` |
| Benchmark | Empirical xdist mode selection | `.github/workflows/pytest-benchmark.yml` matrix | no |
| Nightly | Heavy regression detection | `.github/workflows/nightly-backend-quality.yml` | no |
| Live/manual | Real TDLib/Telegram/S3 validation | `pytest -m live` with explicit secrets | no |

`PYTEST_PROFILE=pr` is the default CI profile. It excludes `contract`, `live`, `integration`, and `slow` markers while keeping strict coverage and branch coverage. The benchmark workflow is the only place where `-n/--dist` mode should be changed experimentally before promoting a new mode into `test-quality.yml`.

## Testing layers

| Layer | Scope | Tool | Run | Marker |
|---|---|---|---|---|
| Unit | Pure business logic, validators, redaction, phone hints | pytest | PR | `unit` |
| API | FastAPI endpoints, auth, roles, workspace scoping | pytest + TestClient | PR | `api` |
| Security | Auth/role matrix, workspace isolation, PII, secrets | pytest + TestClient | PR | `security` |
| Worker | RQ/background-job behavior with deterministic fakes | pytest | PR/nightly | `worker` |
| Architecture | import boundaries, layering, quality constraints | pytest/static checks | PR | `architecture` |
| Property | Hypothesis/property-based checks | pytest + Hypothesis | PR/nightly | `property` |
| Contract | OpenAPI drift, API-client wrapper correctness, Schemathesis | pytest/npm | soft PR/nightly | `contract` |
| Integration | PostgreSQL, Redis, RQ, storage | pytest markers | nightly/manual | `postgres`, `redis`, `integration` |
| Live/manual | TDLib, Telegram, S3, staging | pytest live/manual | manual only | `live` |

## Required test rules

- One test should validate one behavior. Split monster tests or parametrize them.
- Use strict assertions only: `assert`, `assertEqual`, `assertRaises`, `pytest.raises`.
- Use `pytest.mark.parametrize` instead of copy-paste test bodies.
- Mock only real boundaries: I/O, network, DB, time, queues, cloud clients.
- No `sleep()` in PR tests. Use fake clocks, injected state, events, or direct assertions.
- No shared mutable state between tests. Prefer function-scoped fixtures.
- DB-heavy tests must stay explicit and measurable through `fixture-audit.json`.

## CI telemetry

The `backend-tests` job now uploads lightweight artifacts only:

- `coverage.json`
- `coverage.xml`
- `test-quality.sarif`
- `test-quality.json`
- `slow-tests.json`
- `fixture-audit.json`
- `pytest-runtime-summary.txt`
- `pytest.log`

`slow-tests.json` is informational in this phase. Hard thresholds should be added only after a stable baseline is collected.

## Nightly Backend Quality

`.github/workflows/nightly-backend-quality.yml` runs non-required heavy checks:

- `slow or property`
- contract fuzz with larger example budget
- PostgreSQL-marked parity tests with a service container
- selected mutation profile through `scripts/check.py --only mutation` as a soft job

Promote a nightly check to required only after the backlog is empty, runtime is stable, and failures are actionable.

## Tests that must not run in normal PR

- `pytest -m live`
- tests requiring real TDLib, Telegram, S3, Redis, or PostgreSQL unless isolated behind a dedicated marker/profile
- manual operational smoke scripts
- mutation testing
- heavy Schemathesis/property fuzzing
