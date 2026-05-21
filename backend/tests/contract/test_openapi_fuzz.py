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

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, settings as hypothesis_settings

from app.main import app

schemathesis = pytest.importorskip("schemathesis")
schemathesis_checks = pytest.importorskip("schemathesis.checks")


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
#   - max_examples kept LOW (5) — full suite has many endpoints; 5 × ~50 endpoints
#     ≈ 250 generated cases per run. Higher counts add time without much value
#     beyond catching the obvious 500s.
#   - deadline=None — xdist parallelism + ASGI startup spikes can blow defaults.
#   - too_slow ignored for the same reason.
_FUZZ_SETTINGS = hypothesis_settings(
    max_examples=int(os.getenv("SCHEMATHESIS_MAX_EXAMPLES", "5")),
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.function_scoped_fixture,
    ],
)


@pytest.mark.contract
@pytest.mark.allow_pii_in_logs  # Schemathesis emits randomized strings that may match patterns.
@schema.parametrize()
@_FUZZ_SETTINGS
def test_openapi_contract(case: schemathesis.Case, app_client, monkeypatch) -> None:
    """Fuzz a single endpoint operation with schema-valid inputs.

    Schemathesis explodes this parametrization across every (path, method) pair
    in the OpenAPI document. Each invocation runs ``case.call_and_validate()``,
    which performs the request in-process and runs all of Schemathesis's
    built-in checks: no 5xx, declared status code, response schema conformance,
    Content-Type compatibility, etc.

    A failure here is the SUT's fault — either the OpenAPI schema lies about
    the response, or the handler crashes on an input that the schema accepts.
    """
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok"},
    )
    monkeypatch.setattr("app.config.settings.auth_start_cooldown_seconds", 0)
    assert app_client is not None

    excluded_checks = []
    if case.path in _FILE_UPLOAD_PATHS | _BUSINESS_PRECONDITION_PATHS:
        excluded_checks.append(_POSITIVE_DATA_ACCEPTANCE)
    if case.path in _AMBIGUOUS_DYNAMIC_METHOD_PATHS:
        excluded_checks.append(_UNSUPPORTED_METHOD)

    response = case.call_and_validate(excluded_checks=excluded_checks or None)
    assert response.status_code < 500
