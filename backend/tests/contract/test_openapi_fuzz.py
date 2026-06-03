"""OpenAPI-driven contract fuzz tests via Schemathesis.

Schemathesis reads the FastAPI app's OpenAPI schema and generates dozens of
test cases per endpoint with random-but-schema-valid inputs. For every case
we assert:

  - No 5xx response (a 500 means the endpoint crashed on a schema-valid input)
  - Response status code is declared in the OpenAPI spec
  - Response content matches the declared response schema

This catches whole classes of bugs that hand-written tests miss:
  - Edge inputs (empty strings, unicode, negative numbers, max-int)
  - Missing/extra fields
  - Schema drift between code and OpenAPI
  - Unhandled exceptions becoming 500s

We deliberately run in PYTEST mode (in-process ASGI) so no test server is
needed and DB session uses the same overrides as the rest of the suite.

Auth-protected endpoints will mostly return 401/403 — that's correct and
expected. We're testing the SCHEMA contract, not deep business logic.

To allow PII-shaped random data in the log stream (Schemathesis generates
random strings that may match credential patterns by coincidence), this
module uses the @pytest.mark.allow_pii_in_logs opt-out.
"""

# test-analyzer: disable-file=STG007 reason="contract fuzz is not a rate-limit suite" permanent="true"

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import schemathesis
import schemathesis.checks as schemathesis_checks
from hypothesis import HealthCheck, settings as hypothesis_settings
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import app


class _ContractRedis:
    def ping(self) -> bool:
        return True


# Load the OpenAPI schema directly from the FastAPI ASGI app.
schema = schemathesis.openapi.from_asgi("/openapi.json", app)
schemathesis_checks.load_all_checks()

_POSITIVE_DATA_ACCEPTANCE = schemathesis_checks.CHECKS.get_one("positive_data_acceptance")
_UNSUPPORTED_METHOD = schemathesis_checks.CHECKS.get_one("unsupported_method")
_FILE_UPLOAD_PATHS = {
    "/api/assets/profile-audio",
    "/api/assets/profile-photo",
    "/api/assets/story-image",
    "/api/assets/story-video",
}
_BUSINESS_PRECONDITION_PATHS = {
    # Auth batches are stateful/idempotent; after generated accounts exist, a
    # schema-valid request can correctly return AUTH_BATCH_EMPTY.
    "/api/auth-batches",
    # delay_max_seconds must be >= delay_min_seconds; OpenAPI cannot express
    # this cross-field invariant precisely enough for positive-data generation.
    "/api/neuro-commenting/campaigns",
    "/api/neuro-commenting/campaigns/{campaign_id}",
    "/api/warmup/sessions",
}
_AMBIGUOUS_DYNAMIC_METHOD_PATHS = {
    "/api/story-drafts/{account_id}",
    "/api/story-drafts/{draft_id}",
}


# Schemathesis-specific Hypothesis settings:
#   - max_examples defaults to the fast PR profile (1). Scheduled/manual CI can
#     raise SCHEMATHESIS_MAX_EXAMPLES for broader fuzzing.
#   - deadline=None — xdist parallelism + ASGI startup spikes can blow defaults.
#   - too_slow ignored for the same reason.
_FUZZ_SETTINGS = hypothesis_settings(
    max_examples=int(os.getenv("SCHEMATHESIS_MAX_EXAMPLES", "1")),
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.function_scoped_fixture,
    ],
)


@pytest.fixture()
def contract_app_overrides(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply deterministic app overrides before Schemathesis creates its client."""

    monkeypatch.setattr("app.main._maybe_hydrate_rate_limits", lambda: None)
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok"},
    )
    monkeypatch.setattr(
        "app.api.diagnostics.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    monkeypatch.setattr("app.api.diagnostics.redis_from_url", lambda: _ContractRedis())
    monkeypatch.setattr("app.config.settings.auth_start_cooldown_seconds", 0)

    def _override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.mark.contract
@pytest.mark.allow_pii_in_logs  # Schemathesis emits randomized strings that may match patterns.
@schema.parametrize()
@_FUZZ_SETTINGS
def test_openapi_contract(case: schemathesis.Case, contract_app_overrides: None) -> None:
    """Fuzz a single endpoint operation with schema-valid inputs.

    Schemathesis explodes this parametrization across every (path, method) pair
    in the OpenAPI document. Each invocation runs ``case.call_and_validate()``,
    which performs the request in-process and runs all of Schemathesis's
    built-in checks: no 5xx, declared status code, response schema conformance,
    Content-Type compatibility, etc.

    A failure here is the SUT's fault — either the OpenAPI schema lies about
    the response, or the handler crashes on an input that the schema accepts.
    """
    assert contract_app_overrides is None

    excluded_checks = []
    if case.path in _FILE_UPLOAD_PATHS | _BUSINESS_PRECONDITION_PATHS:
        excluded_checks.append(_POSITIVE_DATA_ACCEPTANCE)
    if case.path in _AMBIGUOUS_DYNAMIC_METHOD_PATHS:
        excluded_checks.append(_UNSUPPORTED_METHOD)

    response = case.call_and_validate(excluded_checks=excluded_checks or None)
    assert response.status_code < 500
