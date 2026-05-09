# Risk Register

| Risk | Area | Severity | Mitigation | Test Coverage | Owner |
|---|---|---:|---|---|---|
| Cross-workspace data leak | Workspace isolation | 1 | All queries filter by `workspace_id`; `tenant_scope` helpers enforce scoping | `test_workspace_isolation_matrix.py`, `test_security_regressions.py`, `test_saas_foundation.py` | TBD |
| Viewer PII exposure | Roles / PII | 1 | Viewer role gets `phone_hint` only; response serializers strip `phone_number` for viewer | `test_pii_auth_batches.py` | TBD |
| Admin endpoint exposure | Auth / roles | 1 | `require_role("admin")` on diagnostics, settings, workers; static route audit test | `test_security_endpoint_matrix.py`, `test_operator_guard.py` | TBD |
| Secret leakage in logs/Sentry | Secrets | 1 | `secret_redaction` applied in logging formatters and error handlers | `test_security_regressions.py`, `test_property_security_helpers.py` | TBD |
| API-client drift | Contract | 2 | `check:api` compares live OpenAPI export against committed `openapi.json` | `npm run check:api`, `client.test.ts` | TBD |
| Job race / idempotency issue | Workers | 2 | PostgreSQL advisory locks, idempotency keys workspace-scoped, dedup by intent hash | `test_locking.py`, `test_worker_hardening.py`, `test_auth_batches.py` | TBD |
| Unsafe upload / import | Storage | 2 | `normalize_storage_key` rejects traversal; archive validation rejects symlinks, depth, size | `test_property_security_helpers.py`, `test_security_regressions.py` | TBD |
| Production config misconfiguration | Config | 2 | Pydantic `model_validator` rejects unsafe prod defaults at startup | `test_saas_foundation.py`, `test_cloud_bootstrap_scripts.py` | TBD |
| Broken migration | Database | 2 | `alembic upgrade head` + `migration_smoke` in CI | CI backend job | TBD |
| Stale export / lifecycle data | Data integrity | 3 | TTL-based cleanup, lifecycle state machine tests | `test_account_lifecycle_execution_plane.py` | TBD |

## Severity Scale

- **1** — Critical: data leak, unauthorized access, secret exposure
- **2** — High: contract break, race condition, unsafe defaults
- **3** — Medium: stale data, non-critical inconsistency
