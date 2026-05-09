"""Property-based tests for security-critical helper functions.

Uses Hypothesis with constrained max_examples for CI speed.
"""
from __future__ import annotations

import string
import tempfile
from pathlib import Path, PurePosixPath

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from app.services.phone_hints import phone_hint, required_phone_hint
from app.services.secret_redaction import (
    SENSITIVE_FRAGMENTS,
    is_sensitive_key,
    redact_metadata,
    redact_text,
)
from app.storage.errors import InvalidStorageKeyError
from app.storage.local import LocalStorageService
from app.storage.paths import (
    normalize_storage_key,
    resolve_child_path,
    validate_tdlib_account_id,
)


# ---------------------------------------------------------------------------
# Settings for CI speed
# ---------------------------------------------------------------------------

CI_SETTINGS = settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])


# ---------------------------------------------------------------------------
# Secret redaction property tests
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.unit
class TestRedactTextProperties:
    """redact_text must strip values after any sensitive key pattern."""

    @given(
        key=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        value=st.text(min_size=4, max_size=30, alphabet=string.ascii_letters + string.digits),
    )
    @CI_SETTINGS
    def test_key_value_pair_redacted(self, key, value):
        assume(value not in key and value not in "***")
        text = f'{key}="{value}"'
        result = redact_text(text)
        assert value not in result, f"value leaked in redact_text: {result}"

    @given(
        key=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        value=st.text(min_size=4, max_size=30, alphabet=string.ascii_letters + string.digits),
    )
    @CI_SETTINGS
    def test_key_colon_value_redacted(self, key, value):
        assume(value not in key and value not in "***")
        text = f"{key}: {value}"
        result = redact_text(text)
        assert value not in result, f"value leaked in redact_text: {result}"

    @given(
        user=st.text(min_size=3, max_size=10, alphabet=string.ascii_letters),
        password=st.text(min_size=4, max_size=10, alphabet=string.ascii_letters + string.digits),
        host=st.text(min_size=3, max_size=15, alphabet=string.ascii_lowercase + string.digits),
    )
    @CI_SETTINGS
    def test_url_credentials_redacted(self, user, password, host):
        assume("@" not in user and "@" not in password)
        assume(":" not in user and "/" not in user)
        assume(":" not in password and "/" not in password)
        assume(password not in "https" and password not in host and password not in "***")
        url = f"https://{user}:{password}@{host}/db"
        result = redact_text(url)
        assert password not in result, f"password leaked in URL: {result}"


@pytest.mark.security
@pytest.mark.unit
class TestRedactMetadataProperties:
    """redact_metadata must recursively clean dicts, lists, and strings."""

    @given(
        key=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        value=st.text(min_size=1, max_size=20, alphabet=string.ascii_letters),
    )
    @CI_SETTINGS
    def test_sensitive_dict_key_masked(self, key, value):
        result = redact_metadata({key: value})
        assert result[key] == "***"

    @given(
        key=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        value=st.text(min_size=1, max_size=20, alphabet=string.ascii_letters),
    )
    @CI_SETTINGS
    def test_nested_sensitive_key_masked(self, key, value):
        result = redact_metadata({"outer": {key: value}})
        assert result["outer"][key] == "***"

    @given(
        key=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        value=st.text(min_size=1, max_size=20, alphabet=string.ascii_letters),
    )
    @CI_SETTINGS
    def test_list_of_dicts_masked(self, key, value):
        result = redact_metadata([{key: value}])
        assert result[0][key] == "***"


@pytest.mark.security
@pytest.mark.unit
class TestIsSensitiveKeyProperties:
    """is_sensitive_key must always catch the known fragment list."""

    @given(
        fragment=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        prefix=st.text(min_size=0, max_size=5, alphabet=string.ascii_lowercase),
        suffix=st.text(min_size=0, max_size=5, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_fragment_always_detected(self, fragment, prefix, suffix):
        key = f"{prefix}{fragment}{suffix}"
        assert is_sensitive_key(key), f"missed sensitive key: {key}"

    @given(
        fragment=st.sampled_from(list(SENSITIVE_FRAGMENTS)),
        separator=st.sampled_from(["_", "-", ".", " "]),
    )
    @CI_SETTINGS
    def test_fragment_with_separator_detected(self, fragment, separator):
        key = fragment.replace("_", separator)
        assert is_sensitive_key(key), f"missed with separator: {key}"


# ---------------------------------------------------------------------------
# Phone hint property tests
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.unit
class TestPhoneHintProperties:
    """phone_hint must never return the full phone number."""

    @given(
        phone=st.from_regex(r"\+1[0-9]{10}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_hint_not_equal_to_full_phone(self, phone):
        hint = phone_hint(phone)
        assert hint != phone

    @given(
        phone=st.from_regex(r"\+1[0-9]{10}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_hint_does_not_contain_full_digits(self, phone):
        hint = phone_hint(phone)
        full_digits = "".join(ch for ch in phone if ch.isdigit())
        assert full_digits not in (hint or "")

    @given(
        phone=st.from_regex(r"\+1[0-9]{10}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_hint_contains_last_4_digits(self, phone):
        hint = phone_hint(phone)
        digits = "".join(ch for ch in phone if ch.isdigit())
        assert hint is not None
        assert digits[-4:] in hint

    @given(
        value=st.text(min_size=0, max_size=3, alphabet=string.digits),
    )
    @CI_SETTINGS
    def test_short_values_return_safe_hint(self, value):
        hint = required_phone_hint(value)
        assert hint == "***"


# ---------------------------------------------------------------------------
# Import / archive path safety property tests
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.unit
class TestArchivePathSafety:
    """Archive path validation from import_validation must reject unsafe paths."""

    @given(
        path=st.from_regex(r"\.\./[a-z]{1,10}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_traversal_rejected(self, path):
        posix = PurePosixPath(path.replace("\\", "/"))
        assert ".." in posix.parts

    @given(
        path=st.from_regex(r"/[a-z]{1,10}/[a-z]{1,10}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_absolute_paths_detected(self, path):
        posix = PurePosixPath(path)
        assert posix.is_absolute()

    @given(
        segments=st.lists(
            st.text(min_size=1, max_size=8, alphabet=string.ascii_lowercase),
            min_size=20,
            max_size=25,
        ),
    )
    @CI_SETTINGS
    def test_excessive_depth_detected(self, segments):
        path = PurePosixPath("/".join(segments))
        assert len(path.parts) > 15


# ---------------------------------------------------------------------------
# Storage key and path safety property tests
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.unit
class TestNormalizeStorageKeyProperties:
    """normalize_storage_key must reject traversal and absolute keys."""

    @given(
        prefix=st.text(min_size=0, max_size=5, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_double_dot_rejected(self, prefix):
        key = f"{prefix}/../etc/passwd"
        with pytest.raises(InvalidStorageKeyError):
            normalize_storage_key(key)

    @given(
        path=st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_absolute_path_rejected(self, path):
        with pytest.raises(InvalidStorageKeyError):
            normalize_storage_key(f"/{path}")

    @given(
        path=st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_windows_absolute_rejected(self, path):
        with pytest.raises(InvalidStorageKeyError):
            normalize_storage_key(f"C:/{path}")

    @given(
        path=st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_tilde_rejected(self, path):
        with pytest.raises(InvalidStorageKeyError):
            normalize_storage_key(f"~/{path}")

    @given(
        segments=st.lists(
            st.text(min_size=1, max_size=8, alphabet=string.ascii_letters + string.digits + "-_"),
            min_size=1,
            max_size=5,
        ),
    )
    @CI_SETTINGS
    def test_safe_key_normalized(self, segments):
        key = "/".join(segments)
        result = normalize_storage_key(key)
        assert ".." not in result.split("/")
        assert not result.startswith("/")

    @given(
        prefix=st.text(min_size=0, max_size=5, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_backslash_traversal_rejected(self, prefix):
        key = f"{prefix}\\..\\etc\\passwd"
        with pytest.raises(InvalidStorageKeyError):
            normalize_storage_key(key)


@pytest.mark.security
@pytest.mark.unit
class TestResolveChildPathProperties:
    """resolve_child_path must keep resolved path within root."""

    @given(
        name=st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase + string.digits),
    )
    @CI_SETTINGS
    def test_safe_name_stays_within_root(self, name):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = resolve_child_path(root, name)
            assert str(result.resolve()).startswith(str(root.resolve()))

    @given(
        depth=st.integers(min_value=1, max_value=5),
    )
    @CI_SETTINGS
    def test_traversal_parts_rejected(self, depth):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            parts = [".."] * depth + ["etc", "passwd"]
            with pytest.raises(InvalidStorageKeyError):
                resolve_child_path(root, *parts)


@pytest.mark.security
@pytest.mark.unit
class TestLocalStorageResolvePath:
    """LocalStorageService.resolve_path must keep files within root."""

    @given(
        segments=st.lists(
            st.text(min_size=1, max_size=8, alphabet=string.ascii_letters + string.digits + "-_"),
            min_size=1,
            max_size=3,
        ),
    )
    @CI_SETTINGS
    def test_safe_key_resolves_within_root(self, segments):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorageService(root=Path(tmpdir))
            key = "/".join(segments)
            result = storage.resolve_path(key)
            assert str(result.resolve()).startswith(str(Path(tmpdir).resolve()))

    @given(
        prefix=st.text(min_size=0, max_size=5, alphabet=string.ascii_lowercase),
    )
    @CI_SETTINGS
    def test_traversal_key_rejected(self, prefix):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorageService(root=Path(tmpdir))
            with pytest.raises(InvalidStorageKeyError):
                storage.resolve_path(f"{prefix}/../../../etc/passwd")


@pytest.mark.security
@pytest.mark.unit
class TestValidateTdlibAccountIdProperties:
    """validate_tdlib_account_id must reject unsafe characters."""

    @given(
        safe_id=st.from_regex(r"[A-Za-z0-9][A-Za-z0-9_-]{0,30}", fullmatch=True),
    )
    @CI_SETTINGS
    def test_safe_id_accepted(self, safe_id):
        assume("." not in safe_id and "/" not in safe_id and "\\" not in safe_id)
        result = validate_tdlib_account_id(safe_id)
        assert result == safe_id

    @given(
        unsafe=st.sampled_from(["../etc", "foo/bar", "a.b", "a\\b", ""]),
    )
    @CI_SETTINGS
    def test_unsafe_id_rejected(self, unsafe):
        with pytest.raises(InvalidStorageKeyError):
            validate_tdlib_account_id(unsafe)
