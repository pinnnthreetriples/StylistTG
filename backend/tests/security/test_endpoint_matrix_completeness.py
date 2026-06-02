"""Ratchet completeness check for the RBAC endpoint matrix (issue #269).

Walks every FastAPI route under ``/api/`` and ``/diagnostics/`` and
asserts every mutating route (POST / PATCH / PUT / DELETE) is **either**:

- present in ``ENDPOINT_MATRIX`` from
  :mod:`tests.security.test_security_endpoint_matrix`, or
- recorded in ``tests/security/rbac_matrix_baseline.json`` as a
  pre-existing gap.

The baseline file captures the 90 pre-existing mutating routes that
were not in ENDPOINT_MATRIX when this ratchet landed. New routes MUST
be added to ENDPOINT_MATRIX directly — the baseline is read-only and
should only shrink as the matrix grows.

Adding an entry to the baseline JSON in a PR fails this test: removals
from the baseline are allowed (matrix improvements), additions are not.
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
