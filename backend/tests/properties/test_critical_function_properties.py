"""Property-based tests for critical pure functions.

These tests use Hypothesis to generate hundreds of inputs per run and assert
INVARIANTS that must hold for ALL inputs (not just hand-crafted examples).

A property test fails ⇒ Hypothesis shrinks to the minimal failing input and
reports it. Add the minimal input as a regression example with @example().
"""

from __future__ import annotations

import re
import string

import pytest
from hypothesis import HealthCheck, assume, example, given, settings, strategies as st

from app.adapters.tdlib_auth import normalize_phone_number
from app.services.plan import (
    PROFILE_STEP_TYPES,
    build_profile_plan,
    canonical_payload,
    compute_execution_intent_hash,
)
from app.services.step_registry import (
    SUPPORTED_ACCOUNT_UPDATE_STEP_TYPES,
    validate_account_update_plan_steps,
)


# Tighter Hypothesis settings: deadline=None because xdist workers can spike,
# max_examples=200 for stronger coverage than the default 100.
_PROPERTY_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


# ---------------------------------------------------------------------------
# normalize_phone_number — E.164 validator
# ---------------------------------------------------------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


@given(st.text(max_size=200))
@_PROPERTY_SETTINGS
def test_normalize_phone_number_never_raises_anything_other_than_value_error(text: str) -> None:
    """For ANY input string the function must either return a normalized E.164
    string or raise ValueError. No other exception (TypeError, AttributeError,
    UnicodeError, IndexError, …) is acceptable."""
    try:
        result = normalize_phone_number(text)
    except ValueError:
        return  # expected rejection
    # If it accepted the input, the output must always match E.164.
    assert isinstance(result, str)
    assert _E164_RE.fullmatch(result), f"non-E.164 output {result!r} for input {text!r}"


# Generator for E.164-shaped phone numbers (1-9 leading digit, 8-15 total digits).
_e164_phones = st.from_regex(r"\+[1-9][0-9]{7,14}", fullmatch=True)


@given(_e164_phones)
@_PROPERTY_SETTINGS
@example("+15551234567")
@example("+999999999999999")  # 15 digits — upper boundary of \d{7,14} (1 + 14)
def test_normalize_phone_number_is_idempotent_on_valid_inputs(phone: str) -> None:
    """normalize(normalize(x)) == normalize(x) for all valid E.164 phones."""
    once = normalize_phone_number(phone)
    twice = normalize_phone_number(once)
    assert once == twice == phone


@given(
    _e164_phones,
    st.lists(st.sampled_from(list(" \t\n.-()[]/")), min_size=0, max_size=5),
)
@_PROPERTY_SETTINGS
def test_normalize_phone_number_strips_typical_separators(
    phone: str, separators: list[str]
) -> None:
    """Embedding common formatting separators into a valid phone should still
    normalize to the same canonical value."""
    # Splice separators between every digit of the input number.
    digits = phone[1:]
    spliced = "+" + "".join(
        d + (separators[i % len(separators)] if separators else "") for i, d in enumerate(digits)
    )
    assert normalize_phone_number(spliced) == phone


@given(st.text(alphabet=string.ascii_letters, min_size=1, max_size=50))
@_PROPERTY_SETTINGS
def test_normalize_phone_number_rejects_pure_alpha(text: str) -> None:
    """Letters-only input has no digits ⇒ must raise."""
    with pytest.raises(ValueError):
        normalize_phone_number(text)


# ---------------------------------------------------------------------------
# canonical_payload — projection helper
# ---------------------------------------------------------------------------

_CANONICAL_KEYS = ("name", "bio", "username", "photo_asset_id")


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.none(), st.text(max_size=50), st.integers(), st.booleans()),
        max_size=20,
    )
)
@_PROPERTY_SETTINGS
def test_canonical_payload_always_has_exactly_the_four_canonical_keys(payload: dict) -> None:
    """Output keys are EXACTLY the four canonical fields, regardless of input."""
    result = canonical_payload(payload)
    assert set(result.keys()) == set(_CANONICAL_KEYS)


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.none(), st.text(max_size=50)),
        max_size=20,
    )
)
@_PROPERTY_SETTINGS
def test_canonical_payload_is_idempotent(payload: dict) -> None:
    once = canonical_payload(payload)
    twice = canonical_payload(once)
    assert once == twice


@given(
    st.fixed_dictionaries({k: st.text(max_size=30) for k in _CANONICAL_KEYS}),
    st.dictionaries(
        st.text(min_size=1, max_size=20).filter(lambda k: k not in _CANONICAL_KEYS),
        st.text(max_size=30),
        max_size=10,
    ),
)
@_PROPERTY_SETTINGS
def test_canonical_payload_ignores_unknown_keys(canonical: dict, extras: dict) -> None:
    """Adding arbitrary unknown keys to the input must not change the output."""
    assert canonical_payload({**canonical, **extras}) == canonical_payload(canonical)


# ---------------------------------------------------------------------------
# compute_execution_intent_hash — SHA256 over canonicalized payload
# ---------------------------------------------------------------------------

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


@given(
    st.text(min_size=1, max_size=40),
    st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.none(), st.text(max_size=40)),
        max_size=10,
    ),
)
@_PROPERTY_SETTINGS
def test_compute_execution_intent_hash_shape_is_sha256_hex(account_id: str, payload: dict) -> None:
    h = compute_execution_intent_hash(account_id, payload)
    assert _HEX64_RE.fullmatch(h), f"not a sha256 hex digest: {h!r}"


@given(
    st.text(min_size=1, max_size=40),
    st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.none(), st.text(max_size=40)),
        max_size=10,
    ),
)
@_PROPERTY_SETTINGS
def test_compute_execution_intent_hash_is_deterministic(account_id: str, payload: dict) -> None:
    """Same input ⇒ same hash. Repeated calls never drift."""
    h1 = compute_execution_intent_hash(account_id, payload)
    h2 = compute_execution_intent_hash(account_id, payload)
    assert h1 == h2


@given(
    st.text(min_size=1, max_size=40),
    st.fixed_dictionaries({k: st.text(max_size=30) for k in _CANONICAL_KEYS}),
    st.dictionaries(
        st.text(min_size=1, max_size=20).filter(lambda k: k not in _CANONICAL_KEYS),
        st.text(max_size=30),
        max_size=5,
    ),
)
@_PROPERTY_SETTINGS
def test_compute_execution_intent_hash_ignores_non_canonical_keys(
    account_id: str, canonical: dict, extras: dict
) -> None:
    """Hashing happens over canonical_payload(), so extra keys must not change
    the hash. This is a critical invariant for idempotency."""
    base = compute_execution_intent_hash(account_id, canonical)
    with_noise = compute_execution_intent_hash(account_id, {**canonical, **extras})
    assert base == with_noise


@given(
    st.text(min_size=1, max_size=40),
    st.text(min_size=1, max_size=40),
)
@_PROPERTY_SETTINGS
def test_compute_execution_intent_hash_changes_with_account_id(a: str, b: str) -> None:
    """Different account_ids ⇒ different hashes (for any non-empty payload)."""
    assume(a != b)
    payload = {"name": "test"}
    assert compute_execution_intent_hash(a, payload) != compute_execution_intent_hash(b, payload)


# ---------------------------------------------------------------------------
# build_profile_plan — plan builder
# ---------------------------------------------------------------------------


@given(
    st.fixed_dictionaries(
        {
            "name": st.one_of(st.none(), st.text(max_size=30)),
            "bio": st.one_of(st.none(), st.text(max_size=100)),
            "username": st.one_of(st.none(), st.text(max_size=20)),
            "photo_asset_id": st.one_of(st.none(), st.text(max_size=30)),
        }
    )
)
@_PROPERTY_SETTINGS
def test_build_profile_plan_always_has_four_ordered_steps(payload: dict) -> None:
    plan = build_profile_plan(payload)
    steps = plan["steps"]
    assert len(steps) == 4
    # order is 1-indexed, strictly increasing
    orders = [s["order"] for s in steps]
    assert orders == [1, 2, 3, 4]
    # step types match the canonical list, in order
    assert [s["step_type"] for s in steps] == list(PROFILE_STEP_TYPES)


@given(st.text(max_size=50))
@_PROPERTY_SETTINGS
def test_build_profile_plan_splits_name_into_first_and_last(name: str) -> None:
    """For any name input, set_name step contains first/last consistent with split."""
    plan = build_profile_plan({"name": name})
    set_name_step = next(s for s in plan["steps"] if s["step_type"] == "set_name")
    inner = set_name_step["payload"]
    parts = name.split(maxsplit=1)
    expected_first = parts[0] if parts else ""
    expected_last = parts[1] if len(parts) > 1 else ""
    assert inner["first_name"] == expected_first
    assert inner["last_name"] == expected_last


# ---------------------------------------------------------------------------
# validate_account_update_plan_steps — step-type whitelist enforcer
# ---------------------------------------------------------------------------


@given(
    st.lists(
        st.fixed_dictionaries(
            {"step_type": st.sampled_from(list(SUPPORTED_ACCOUNT_UPDATE_STEP_TYPES))}
        ),
        max_size=10,
    )
)
@_PROPERTY_SETTINGS
def test_validate_plan_accepts_any_subset_of_supported_steps(steps: list[dict]) -> None:
    """All-supported step types ⇒ never raises."""
    assert validate_account_update_plan_steps({"steps": steps}) is None


@given(
    # Step type that is GUARANTEED not in the supported set.
    st.text(min_size=1, max_size=30).filter(lambda s: s not in SUPPORTED_ACCOUNT_UPDATE_STEP_TYPES)
)
@_PROPERTY_SETTINGS
def test_validate_plan_rejects_unknown_step_type(bad_type: str) -> None:
    with pytest.raises(ValueError, match="unsupported account update step type"):
        validate_account_update_plan_steps({"steps": [{"step_type": bad_type}]})


def test_validate_plan_empty_steps_is_a_noop() -> None:
    """Boundary: an empty plan must not raise."""
    assert validate_account_update_plan_steps({"steps": []}) is None
    assert validate_account_update_plan_steps({}) is None
