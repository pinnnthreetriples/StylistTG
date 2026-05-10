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
| `unit` | Pure unit tests — no DB, no HTTP, no external services |
| `api` | FastAPI endpoint tests via TestClient |
| `security` | Auth, role, workspace isolation, and PII tests |
| `postgres` | Requires real PostgreSQL (CI service container) |
| `redis` | Requires real Redis |
| `contract` | API/OpenAPI/client contract tests |
| `integration` | Broader integration tests requiring external services |
| `live` | External services / TDLib / Telegram — never in normal CI |

## Running by Marker

```bash
python -m pytest -m unit
python -m pytest -m security
python -m pytest -m "not live"
python -m pytest -m "api and not live"
```

## Coverage

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## Parallel Execution

```bash
python -m pytest -n auto   # requires pytest-xdist
```

## Key Fixtures

Defined in `conftest.py`:

- **`db_session`** — In-memory SQLite session with all tables created
- **`storage_dir`** — Temporary directory for storage tests
- **`FakeExecutionUsableAdapter`** — Configurable fake for runtime checks
- **`FakeProfileSyncAdapter`** — Fake profile sync with call recording
- **`FakeTdlibAuthAdapter`** — Configurable fake for TDLib OTP auth

## Test File Conventions

- `test_security_endpoint_matrix.py` — Data-driven role/auth matrix
- `test_workspace_isolation_matrix.py` — Cross-workspace negative tests
- `test_pii_auth_batches.py` — PII visibility per role
- `test_property_security_helpers.py` — Hypothesis property-based tests
- `test_security_regressions.py` — Regression tests for security fixes
- `test_saas_foundation.py` — SaaS infrastructure and config tests

## Adding a New Endpoint to the Security Matrix

Add one tuple to the `ENDPOINT_MATRIX` list in `test_security_endpoint_matrix.py`:

```python
("GET", "/api/new-endpoint", "viewer", False),
```

Fields: `(method, path, min_role, is_mutation)`
