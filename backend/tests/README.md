# Backend Tests

## Quick Start

```bash
cd backend
pip install -e ".[dev]"
python -m pytest
```

## Test Markers

| Marker | Description |
|---|---|
| `unit` | Isolated unit-level tests — no HTTP or external services; may use in-memory SQLite |
| `api` | FastAPI endpoint tests via TestClient |
| `security` | Auth, role, workspace isolation, and PII tests |
| `postgres` | Requires real PostgreSQL (CI service container) |
| `redis` | Requires real Redis |
| `contract` | API/OpenAPI/client contract tests |
| `slow` | Expensive tests that normally belong in nightly/full CI |
| `integration` | Broader integration tests requiring external services |
| `live` | External services / TDLib / Telegram — never in normal CI |

## Running by Marker

```bash
python -m pytest -m unit
python -m pytest -m security
python -m pytest -m "not slow and not live"
python -m pytest -m "api and not live"
```

Markers are applied first to current high-value suites; older tests may remain unmarked until touched.

## Coverage

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## Parallel Execution

```bash
python -m pytest -n auto   # requires pytest-xdist
```

Parallel execution is a local compatibility trial only. Do not enable `-n auto` in CI until a full run is known to be stable.

## Slow Test Measurement

```bash
python -m pytest --durations=25
```

## Key Fixtures

Defined in `conftest.py`:

- **`db_session`** — In-memory SQLite session with all tables created
- **`storage_dir`** — Temporary directory for storage tests
- **`FakeExecutionUsableAdapter`** — Configurable fake for runtime checks
- **`FakeProfileSyncAdapter`** — Fake profile sync with call recording
- **`FakeTdlibAuthAdapter`** — Configurable fake for TDLib OTP auth

Defined under `tests/helpers/`:

- **`app.app_client`** — FastAPI TestClient context manager that overrides `get_session` and auth context, then clears dependency overrides.
- **`factories.make_session`** — SQLite session factory plus engine with metadata initialized.
- **`factories.seed_account` / `seed_account_with_profile`** — Common account seeds.
- **`factories.seed_auth_batch` / `seed_profile_job` / `seed_asset`** — Shared entity seeds for regression tests.
- **`query_count.QueryCounter`** — SQL query counting context manager.

## Test File Conventions

- `test_security_endpoint_matrix.py` — Data-driven role/auth matrix
- `test_workspace_isolation_matrix.py` — Cross-workspace negative tests
- `test_pii_auth_batches.py` — PII visibility per role
- `test_property_security_helpers.py` — Hypothesis property-based tests
- `test_security_regressions.py` — Regression tests for security fixes
- `test_query_count_foundation.py` — QueryCounter helper sanity tests
- `test_query_count_regressions.py` — Strict endpoint query-count ceilings
- `test_worker_reliability.py` — Worker lock retry, queue reconciliation, and RQ retry adapter tests
- `test_saas_foundation.py` — SaaS infrastructure and config tests

## Adding a New Endpoint to the Security Matrix

Add one tuple to the `ENDPOINT_MATRIX` list in `test_security_endpoint_matrix.py`:

```python
("GET", "/api/new-endpoint", "viewer", False),
```

Fields: `(method, path, min_role, is_mutation)`
