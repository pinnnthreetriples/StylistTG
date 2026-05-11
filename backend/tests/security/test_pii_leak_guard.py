"""Verify the autouse PII-leak guard in conftest.py actually catches leaks.

These tests run the SAME guard against synthetic log records to assert it
fires on real-looking secrets and stays quiet for redacted / test-fixture
values. If any of these tests starts failing, the guard is no longer
protecting CI from accidental credential leaks.
"""

from __future__ import annotations

import logging
import re

import pytest

# Re-import the private patterns from conftest. They're intentionally private
# at the module level (start with `_`) — accessing them here is justified by
# the contract that this test pins their behavior.
from tests.conftest import _SENSITIVE_PATTERNS


# ---------------------------------------------------------------------------
# Direct pattern tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "leak_sample,expected_label",
    [
        # JWT token (signed, three-part base64url with dot separators).
        (
            "auth response token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.abc12345",
            "JWT token",
        ),
        # TDLib api_hash in dict/repr style with 32 hex chars.
        (
            "config: {'api_hash': 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6'}",
            "TDLib api_hash",
        ),
        # api_hash variant: key=value style, kebab-case key.
        (
            "TDLIB_API_HASH=0123456789abcdef0123456789abcdef",
            "TDLib api_hash",
        ),
        # session_string with base64-ish blob.
        (
            "session_string='AgABAAEAUgIIAAAAQwSDwAAAAAQA1234567890ABCDEFghij'",
            "TDLib session_string",
        ),
        # Authorization header dumped raw.
        (
            "Authorization: Bearer abc.def.ghi.jkl.mno.pqr.stuv",
            "Bearer header",
        ),
        # Generic password field unredacted.
        (
            "user payload: {'password': 'hunter2hunter2'}",
            "credential field",
        ),
        # secret= unredacted.
        (
            "config secret=supersecretvalue123",
            "credential field",
        ),
    ],
)
def test_patterns_match_real_leaks(leak_sample: str, expected_label: str) -> None:
    matches: list[str] = [
        label for pattern, label in _SENSITIVE_PATTERNS if pattern.search(leak_sample)
    ]
    assert expected_label in matches, (
        f"expected {expected_label!r} to fire on sample {leak_sample!r}, got {matches}"
    )


@pytest.mark.parametrize(
    "safe_sample",
    [
        # Common test fixture phone — not a credential, must NOT match.
        "starting OTP for phone=+15551234567",
        # Redacted password.
        "user payload: {'password': '***'}",
        "config: secret=[REDACTED]",
        "credentials: password='<redacted>'",
        # Empty value.
        "secret=''",
        "password: None",
        # api_hash with a non-hex placeholder.
        "api_hash='REDACTED'",
        # Short bearer (likely truncated/redacted form).
        "Authorization: Bearer abc",
        # JWT-looking but missing the signed structure (only one segment).
        "token marker: eyJsomething",
        # session_string with explicit redaction marker.
        "session_string='***'",
    ],
)
def test_patterns_do_not_fire_on_safe_values(safe_sample: str) -> None:
    matches: list[str] = [
        label for pattern, label in _SENSITIVE_PATTERNS if pattern.search(safe_sample)
    ]
    assert matches == [], f"unexpected leak detection on safe sample {safe_sample!r}: {matches}"


# ---------------------------------------------------------------------------
# Integration: the autouse fixture itself fires pytest.fail when a leak happens.
# ---------------------------------------------------------------------------


def test_guard_uses_search_not_fullmatch() -> None:
    """The patterns must be substring matches, not full-string matches, so a
    leak embedded inside a larger log line is still detected."""
    surrounded = (
        "INFO: processing request for user 42 "
        "with TDLIB_API_HASH=0123456789abcdef0123456789abcdef "
        "trace_id=abc-def"
    )
    matches = [label for pattern, label in _SENSITIVE_PATTERNS if pattern.search(surrounded)]
    assert "TDLib api_hash" in matches


# ---------------------------------------------------------------------------
# Opt-out marker: tests that intentionally feed PII through the SUT skip the guard.
# ---------------------------------------------------------------------------


@pytest.mark.allow_pii_in_logs
def test_marker_opt_out_allows_intentional_leak(caplog: pytest.LogCaptureFixture) -> None:
    """A test marked allow_pii_in_logs may log raw secrets without the guard firing.

    Used by redaction tests that need to feed real credential shapes through
    production logging to assert redaction happens downstream.
    """
    logger = logging.getLogger("test.pii_optout")
    with caplog.at_level(logging.INFO, logger=logger.name):
        # This would normally fail the guard.
        logger.info("simulated leak api_hash=%s", "0123456789abcdef0123456789abcdef")

    # The test itself doesn't assert anything about redaction — that's the
    # production-side responsibility. We only verify the guard didn't abort us.
    assert any("api_hash=" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Regression: pattern compile-time invariants.
# ---------------------------------------------------------------------------


def test_all_patterns_are_compiled_regex() -> None:
    assert _SENSITIVE_PATTERNS, "guard has no patterns — coverage is zero"
    for pattern, label in _SENSITIVE_PATTERNS:
        assert isinstance(pattern, re.Pattern), f"{label} is not a compiled regex"
        assert label, "each pattern must have a non-empty label for error messages"
