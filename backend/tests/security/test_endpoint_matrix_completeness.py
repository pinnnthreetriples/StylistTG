"""Ratchet completeness check for the RBAC endpoint matrix (issue #269).

Walks every FastAPI route under ``/api/`` and ``/diagnostics/`` and
asserts every mutating route (POST / PATCH / PUT / DELETE) is **either**:

- present in ``ENDPOINT_MATRIX`` from
  :mod:`tests.security.test_security_endpoint_matrix`, or
- recorded in ``tests/security/rbac_matrix_baseline.json`` as a
  pre-existing gap.

The baseline file captures the 53 pre-existing mutating routes that
were not in ENDPOINT_MATRIX when this ratchet landed. New routes MUST
be added to ENDPOINT_MATRIX directly — the baseline is **immutable**
and may only shrink as the matrix grows.

``EXPECTED_BASELINE_GAPS`` is the frozen set of routes the baseline
was permitted to contain on day one. The ratchet test asserts
``_baseline_keys() <= EXPECTED_BASELINE_GAPS`` — any new key in the
JSON that is not in this constant fails the gate. To grow the
matrix, remove the entry from BOTH the JSON and this constant in
the same PR.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.security.test_security_endpoint_matrix import ENDPOINT_MATRIX

pytestmark = [pytest.mark.security, pytest.mark.unit]


_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
_BASELINE_PATH = Path(__file__).with_name("rbac_matrix_baseline.json")

# Immutable upper bound for the baseline set. The ratchet enforces
# `_baseline_keys() <= EXPECTED_BASELINE_GAPS`: new routes cannot be
# added stealthily, only removed (matrix improvements). When the matrix
# grows to cover a previously-baselined route, remove that entry from
# BOTH the JSON file AND this constant in the same PR — that change is
# trivially visible in code review.
EXPECTED_BASELINE_GAPS: frozenset[tuple[str, str]] = frozenset({
    ("DELETE", "/api/accounts/{account_id}"),
    ("DELETE", "/api/accounts/{account_id}/proxy"),
    ("DELETE", "/api/jobs/{job_id}"),
    ("DELETE", "/api/story-drafts/{draft_id}"),
    ("DELETE", "/api/story-posts/{story_post_id}"),
    ("DELETE", "/api/warmup/sessions/{session_id}"),
    ("PATCH", "/api/story-drafts/{draft_id}"),
    ("POST", "/api/account-import-batches/{batch_id}/confirm"),
    ("POST", "/api/account-import-batches/{batch_id}/validate"),
    ("POST", "/api/account-update/jobs"),
    ("POST", "/api/account-update/preview"),
    ("POST", "/api/accounts/auth-sessions"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/cancel"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/code"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/password"),
    ("POST", "/api/accounts/refresh-runtime"),
    ("POST", "/api/accounts/safety-batch-preview"),
    ("POST", "/api/accounts/{account_id}/bought-onboarding/start"),
    ("POST", "/api/accounts/{account_id}/deletion-requests"),
    ("POST", "/api/accounts/{account_id}/export-requests"),
    ("POST", "/api/accounts/{account_id}/proxy/check"),
    ("POST", "/api/accounts/{account_id}/quarantine/admin-override"),
    ("POST", "/api/accounts/{account_id}/quarantine/release"),
    ("POST", "/api/accounts/{account_id}/reauth-sessions"),
    ("POST", "/api/accounts/{account_id}/refresh-runtime"),
    ("POST", "/api/accounts/{account_id}/safety-overrides"),
    ("POST", "/api/accounts/{account_id}/terminal-status/clear"),
    ("POST", "/api/accounts/{account_id}/validity-check"),
    ("POST", "/api/assets/profile-audio"),
    ("POST", "/api/assets/profile-photo"),
    ("POST", "/api/assets/story-image"),
    ("POST", "/api/assets/story-video"),
    ("POST", "/api/auth-batches/validate-phones"),
    ("POST", "/api/auth-batches/{batch_id}/cancel"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/cancel"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/request-new-code"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/retry"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/submit-2fa"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/submit-code"),
    ("POST", "/api/auth-batches/{batch_id}/pause"),
    ("POST", "/api/auth-batches/{batch_id}/resume"),
    ("POST", "/api/auth-batches/{batch_id}/start"),
    ("POST", "/api/auth/otp/confirm"),
    ("POST", "/api/auth/otp/start"),
    ("POST", "/api/auth/password"),
    ("POST", "/api/jobs/profile"),
    ("POST", "/api/jobs/profile/preview"),
    ("POST", "/api/jobs/{job_id}/cancel"),
    ("POST", "/api/warmup/sessions"),
    ("POST", "/api/warmup/validate"),
    ("PUT", "/api/accounts/{account_id}/proxy"),
    ("PUT", "/api/warmup/sessions/{session_id}/pause"),
    ("PUT", "/api/warmup/sessions/{session_id}/resume"),
})


def _matrix_keys() -> set[tuple[str, str]]:
    return {(method.upper(), path) for method, path, _role, _is_mut in ENDPOINT_MATRIX}


def _baseline_keys() -> set[tuple[str, str]]:
    if not _BASELINE_PATH.is_file():
        return set()
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    return {(method.upper(), path) for method, path in payload.get("baseline_gaps", [])}


def _mutating_app_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if not (path.startswith("/api/") or path.startswith("/diagnostics/")):
            continue
        for method in route.methods or set():
            if method.upper() in _MUTATING_METHODS:
                routes.append((method.upper(), path))
    return routes


def test_new_mutating_routes_must_join_endpoint_matrix() -> None:
    """A new mutating route that isn't in the matrix or the baseline fails."""
    declared = _matrix_keys()
    baseline = _baseline_keys()
    discovered = _mutating_app_routes()

    truly_missing = [
        (method, path)
        for method, path in discovered
        if (method, path) not in declared and (method, path) not in baseline
    ]

    assert not truly_missing, (
        "New mutating /api/ or /diagnostics/ route must be added to "
        "tests/security/test_security_endpoint_matrix.py::ENDPOINT_MATRIX. "
        "Do NOT add it to the baseline. "
        f"Missing from matrix: {truly_missing}"
    )


def test_baseline_is_subset_of_expected() -> None:
    """The baseline ratchet is immutable: only EXPECTED_BASELINE_GAPS keys allowed.

    Any key present in the JSON file but missing from
    ``EXPECTED_BASELINE_GAPS`` fails the gate. This blocks the
    "just-add-it-to-the-baseline" escape valve a developer might try
    when failing the ENDPOINT_MATRIX check.
    """
    baseline = _baseline_keys()
    illegal_additions = sorted(baseline - EXPECTED_BASELINE_GAPS)
    assert not illegal_additions, (
        "Routes were added to rbac_matrix_baseline.json that are NOT in "
        "EXPECTED_BASELINE_GAPS. New routes must go into ENDPOINT_MATRIX, "
        "not into the baseline. "
        f"Illegal baseline additions: {illegal_additions}"
    )


def test_baseline_does_not_grow() -> None:
    """The baseline ratchet is read-only: routes can leave but not enter."""
    baseline = _baseline_keys()
    declared = _matrix_keys()
    # A baseline entry is acceptable only if the route still exists in the app
    # and is not yet in the matrix. Once the matrix covers it, the baseline
    # entry should be removed (matrix improvement). If both contain the same
    # entry, prefer the matrix.
    discovered = set(_mutating_app_routes())

    overlap_with_matrix = sorted(baseline & declared)
    assert not overlap_with_matrix, (
        "Baseline contains routes that are already in ENDPOINT_MATRIX. "
        "Remove them from rbac_matrix_baseline.json — the ratchet only "
        f"shrinks. Overlap: {overlap_with_matrix}"
    )

    obsolete = sorted(baseline - discovered)
    assert not obsolete, (
        "Baseline references routes that no longer exist in the app. "
        f"Remove them from rbac_matrix_baseline.json. Obsolete: {obsolete}"
    )


def test_endpoint_matrix_has_no_stale_entries() -> None:
    declared = _matrix_keys()
    discovered = {(method, path) for method, path in _mutating_app_routes()}
    stale = [
        (method, path)
        for method, path in declared
        if method in _MUTATING_METHODS and (method, path) not in discovered
    ]
    assert not stale, (
        "ENDPOINT_MATRIX references mutating routes that no longer exist in "
        f"the app. Stale: {stale}"
    )
