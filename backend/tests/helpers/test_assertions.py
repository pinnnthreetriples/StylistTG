"""Tests for the strict assertion helpers (issue #263)."""

from __future__ import annotations

# test-analyzer: disable-file=TQA020 reason="false positive: tests exercise the assert_exact_calls/assert_queue_not_called helpers themselves; verification is the assertion helper under test." permanent="true"

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers.assertions import (
    assert_error_response,
    assert_exact_calls,
    assert_foreign_workspace_denied,
    assert_keys_subset,
    assert_no_jobs_created,
    assert_no_sensitive_values,
    assert_queue_not_called,
    assert_rfc3339_aware,
)

pytestmark = pytest.mark.unit


@dataclass
class _FakeResponse:
    status_code: int
    body: Any = field(default=None)

    def json(self) -> Any:
        return self.body


# ---- assert_error_response ---------------------------------------------------


def test_assert_error_response_accepts_exact_envelope() -> None:
    response = _FakeResponse(
        status_code=403,
        body={"error_code": "FORBIDDEN", "message": "forbidden", "field_errors": []},
    )
    assert_error_response(
        response,
        status_code=403,
        error_code="FORBIDDEN",
        field_errors=[],
    )


def test_assert_error_response_rejects_wrong_status() -> None:
    response = _FakeResponse(status_code=500, body={"error_code": "FORBIDDEN"})
    with pytest.raises(AssertionError, match="expected status 403, got 500"):
        assert_error_response(response, status_code=403, error_code="FORBIDDEN")


def test_assert_error_response_rejects_wrong_error_code() -> None:
    response = _FakeResponse(status_code=401, body={"error_code": "OTHER"})
    with pytest.raises(AssertionError, match="expected error_code='AUTH_REQUIRED'"):
        assert_error_response(response, status_code=401, error_code="AUTH_REQUIRED")


def test_assert_error_response_supports_detail_envelope() -> None:
    response = _FakeResponse(status_code=422, body={"detail": "field x is required"})
    assert_error_response(response, status_code=422, detail="field x is required")


def test_assert_error_response_fails_on_non_object_body() -> None:
    response = _FakeResponse(status_code=400, body="raw text")
    with pytest.raises(AssertionError, match="must be a JSON object"):
        assert_error_response(response, status_code=400, error_code="X")


# ---- assert_rfc3339_aware ----------------------------------------------------


def test_assert_rfc3339_aware_accepts_z_suffix() -> None:
    parsed = assert_rfc3339_aware("2026-06-02T01:23:45Z")
    assert parsed == datetime(2026, 6, 2, 1, 23, 45, tzinfo=UTC)


def test_assert_rfc3339_aware_accepts_offset() -> None:
    parsed = assert_rfc3339_aware("2026-06-02T01:23:45+02:00")
    assert parsed.utcoffset() is not None


def test_assert_rfc3339_aware_rejects_naive() -> None:
    with pytest.raises(AssertionError, match="must be timezone-aware"):
        assert_rfc3339_aware("2026-06-02T01:23:45")


def test_assert_rfc3339_aware_rejects_garbage() -> None:
    with pytest.raises(AssertionError, match="not RFC3339-parseable"):
        assert_rfc3339_aware("not a date")


def test_assert_rfc3339_aware_rejects_non_string() -> None:
    with pytest.raises(AssertionError, match="expected RFC3339 string"):
        assert_rfc3339_aware(12345)  # type: ignore[arg-type]


# ---- assert_no_sensitive_values ----------------------------------------------


def test_assert_no_sensitive_values_passes_when_clean() -> None:
    assert_no_sensitive_values({"name": "alice"}, ["password-1", "secret-token"])


def test_assert_no_sensitive_values_detects_leak() -> None:
    payload = {"log": "user logged in with token=abc123"}
    with pytest.raises(AssertionError, match="leaked sensitive values"):
        assert_no_sensitive_values(payload, ["abc123"])


def test_assert_no_sensitive_values_ignores_empty_forbidden() -> None:
    # Empty strings would trivially match anything; helper must skip them.
    assert_no_sensitive_values({"x": "y"}, ["", None])  # type: ignore[list-item]


# ---- assert_foreign_workspace_denied -----------------------------------------


def test_assert_foreign_workspace_denied_passes_with_404() -> None:
    response = _FakeResponse(status_code=404, body={"error_code": "ACCOUNT_NOT_FOUND"})
    assert_foreign_workspace_denied(response)


def test_assert_foreign_workspace_denied_rejects_403() -> None:
    response = _FakeResponse(status_code=403, body={"error_code": "FORBIDDEN"})
    with pytest.raises(AssertionError, match="must return 404"):
        assert_foreign_workspace_denied(response)


def test_assert_foreign_workspace_denied_detects_id_leak() -> None:
    response = _FakeResponse(
        status_code=404,
        body={"error_code": "ACCOUNT_NOT_FOUND", "hint": "account acc-foreign-1 not in workspace"},
    )
    with pytest.raises(AssertionError, match="leaked sensitive values"):
        assert_foreign_workspace_denied(response, foreign_id="acc-foreign-1")


def test_assert_foreign_workspace_denied_accepts_custom_error_code() -> None:
    response = _FakeResponse(status_code=404, body={"error_code": "JOB_NOT_FOUND"})
    assert_foreign_workspace_denied(response, error_code="JOB_NOT_FOUND")


# ---- assert_no_jobs_created --------------------------------------------------


class _FakeQuery:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class _FakeSession:
    def __init__(self, count: int) -> None:
        self._count = count

    def query(self, *_args: object, **_kwargs: object) -> _FakeQuery:
        return _FakeQuery(self._count)


class _DummyJob:
    pass


def test_assert_no_jobs_created_passes_when_empty() -> None:
    assert_no_jobs_created(_FakeSession(0), _DummyJob)


def test_assert_no_jobs_created_fails_when_rows_exist() -> None:
    with pytest.raises(AssertionError, match="must not persist _DummyJob rows, found 2"):
        assert_no_jobs_created(_FakeSession(2), _DummyJob)


# ---- mock helpers ------------------------------------------------------------


class _FakeMock:
    def __init__(self) -> None:
        self.called = False
        self.call_count = 0
        self.call_args_list: list[Any] = []

    def fire(self, *args: object) -> None:
        self.called = True
        self.call_count += 1
        self.call_args_list.append(args)


def test_assert_queue_not_called_passes_for_unused() -> None:
    assert_queue_not_called(_FakeMock())


def test_assert_queue_not_called_fails_when_called() -> None:
    mock = _FakeMock()
    mock.fire("anything")
    with pytest.raises(AssertionError, match="expected queue mock to be untouched"):
        assert_queue_not_called(mock)


def test_assert_exact_calls_matches_sequence() -> None:
    mock = _FakeMock()
    mock.fire("a")
    mock.fire("b")
    assert_exact_calls(mock, ("a",), ("b",))


def test_assert_exact_calls_rejects_extra_calls() -> None:
    mock = _FakeMock()
    mock.fire("a")
    mock.fire("b")
    with pytest.raises(AssertionError, match="expected exact call sequence"):
        assert_exact_calls(mock, ("a",))


# ---- assert_keys_subset ------------------------------------------------------


def test_assert_keys_subset_passes_when_complete() -> None:
    assert_keys_subset({"a": 1, "b": 2, "c": 3}, ["a", "b"])


def test_assert_keys_subset_reports_missing_keys() -> None:
    with pytest.raises(AssertionError, match="missing required keys \\['x'\\]"):
        assert_keys_subset({"a": 1}, ["a", "x"])
