"""Strict assertion helpers for API/security/storage/worker tests (issue #263).

Helpers use plain ``assert`` internally so pytest assertion introspection
shows useful diffs on failure. They do not hide diagnostics. They accept
``object`` / ``Mapping`` instead of the specific response/session types so a
single helper covers FastAPI ``TestClient.Response``, ``httpx.Response``, and
plain ``dict`` payloads.

Helpers must be tested. See ``backend/tests/helpers/test_assertions.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class _HasStatusAndJson(Protocol):
    status_code: int

    def json(self) -> Any: ...  # pragma: no cover - structural


def _json_body(response: _HasStatusAndJson) -> Any:
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001 — surface decoding errors precisely.
        raise AssertionError(
            f"expected JSON response body, got status={response.status_code}; "
            f"json() raised {type(exc).__name__}: {exc}"
        ) from exc


def assert_error_response(
    response: _HasStatusAndJson,
    *,
    status_code: int,
    error_code: str | None = None,
    detail: Any = None,
    field_errors: list[Any] | None = None,
) -> None:
    """Assert a FastAPI/StylistTG error envelope precisely.

    - ``error_code``: expected ``body["error_code"]``. Omit for endpoints that
      use FastAPI's default ``{"detail": ...}`` envelope; pass ``detail=`` instead.
    - ``detail``: expected ``body["detail"]`` exactly (string or list, FastAPI
      validation errors). Used when the endpoint does not emit ``error_code``.
    - ``field_errors``: expected ``body["field_errors"]`` exactly. Omit when the
      endpoint never emits field errors.
    """
    assert response.status_code == status_code, (
        f"expected status {status_code}, got {response.status_code}; body={_json_body(response)!r}"
    )
    body = _json_body(response)
    assert isinstance(body, dict), (
        f"error response must be a JSON object, got {type(body).__name__}"
    )

    if error_code is not None:
        assert body.get("error_code") == error_code, (
            f"expected error_code={error_code!r}, got {body.get('error_code')!r}; body={body!r}"
        )

    if detail is not None:
        assert body.get("detail") == detail, (
            f"expected detail={detail!r}, got {body.get('detail')!r}; body={body!r}"
        )

    if field_errors is not None:
        assert body.get("field_errors") == field_errors, (
            f"expected field_errors={field_errors!r}, got {body.get('field_errors')!r}; "
            f"body={body!r}"
        )


def assert_rfc3339_aware(value: str) -> datetime:
    """Parse-aware RFC3339 datetime check. Returns the parsed datetime.

    Rejects values that are not timezone-aware. Useful for asserting API
    response timestamps without resorting to ``endswith("Z") or "+" in value``.
    """
    assert isinstance(value, str), f"expected RFC3339 string, got {type(value).__name__}"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"value {value!r} is not RFC3339-parseable: {exc}") from exc
    assert parsed.tzinfo is not None and parsed.utcoffset() is not None, (
        f"RFC3339 timestamps must be timezone-aware, got naive value {value!r}"
    )
    return parsed


def assert_no_sensitive_values(serialized: object, forbidden_values: Iterable[str]) -> None:
    """Assert that a response payload contains none of the forbidden substrings.

    Compares the ``str(serialized)`` projection so it catches the value whether
    it appears in a field, an error message, or an embedded log line.
    """
    text = str(serialized)
    leaks = [v for v in forbidden_values if v and v in text]
    assert not leaks, (
        f"response leaked sensitive values {leaks!r}. Forbidden: {list(forbidden_values)!r}. "
        f"Serialized payload: {text[:500]!r}"
    )


def assert_foreign_workspace_denied(
    response: _HasStatusAndJson,
    *,
    error_code: str = "ACCOUNT_NOT_FOUND",
    foreign_id: str | None = None,
) -> None:
    """Assert a foreign-workspace lookup is denied without leaking identifiers.

    Foreign-workspace probes must return 404 (not 403 — that would confirm
    existence) and must not embed the foreign object id in the response.
    """
    assert response.status_code == 404, (
        f"foreign workspace probe must return 404, got {response.status_code}"
    )
    body = _json_body(response)
    if isinstance(body, dict) and "error_code" in body:
        assert body["error_code"] == error_code, (
            f"expected error_code={error_code!r}, got {body.get('error_code')!r}"
        )
    if foreign_id is not None:
        assert_no_sensitive_values(body, [foreign_id])


@runtime_checkable
class _SupportsCount(Protocol):
    def query(self, *args: object, **kwargs: object) -> Any: ...  # pragma: no cover


def assert_no_jobs_created(session: _SupportsCount, model: type[Any]) -> None:
    """Assert that a failure path created no rows of ``model`` in ``session``.

    Use after exercising a denied or invalid request to prove the failure was
    side-effect-free.
    """
    count = session.query(model).count()
    assert count == 0, f"failure path must not persist {model.__name__} rows, found {count}"


@runtime_checkable
class _MockLike(Protocol):
    called: bool
    call_count: int
    call_args_list: list[Any]


def assert_queue_not_called(mock: _MockLike) -> None:
    """Strict ``mock.called is False`` check with a helpful failure message.

    Replaces ``assert not mock.called`` / ``assert mock.call_count == 0`` which
    are easy to invert by accident.
    """
    assert mock.called is False and mock.call_count == 0, (
        f"expected queue mock to be untouched, but it was called "
        f"{mock.call_count} times: {mock.call_args_list!r}"
    )


def assert_exact_calls(mock: _MockLike, *expected_calls: Any) -> None:
    """Assert ``mock.call_args_list == [expected_calls...]`` exactly.

    Use instead of ``mock.assert_called`` / ``mock.call_count > 0``.
    """
    actual = list(mock.call_args_list)
    expected = list(expected_calls)
    assert actual == expected, f"expected exact call sequence {expected!r}, got {actual!r}"


def assert_keys_subset(payload: Mapping[str, Any], required: Iterable[str]) -> None:
    """Assert that ``payload`` contains every key in ``required``.

    Use as a *first* check before asserting individual values; avoids ambiguous
    ``"key" in payload`` checks scattered across a test.
    """
    missing = [k for k in required if k not in payload]
    assert not missing, f"payload missing required keys {missing!r}; got keys={sorted(payload)!r}"
