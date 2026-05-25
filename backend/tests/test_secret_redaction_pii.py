"""Coverage for the redact_pii() recursive PII redactor (audit B F-001).

Three layers under test:
1. Key-based masking (email/phone keys → type-specific tokens).
2. Pattern-based masking (regex-matched emails/phones inside arbitrary strings).
3. Recursive nesting through dict/list/tuple containers.

End-to-end coverage through record_sensitive_audit_event ensures the DB-stored
metadata is sanitized before insert.
"""

from __future__ import annotations

import pytest

from app.services.secret_redaction import (
    REDACTED_EMAIL,
    REDACTED_PHONE,
    redact_pii,
    redact_text,
)


class TestRedactPiiKeyBased:
    def test_email_key_masked(self) -> None:
        assert redact_pii({"email": "alice@example.com"}) == {"email": REDACTED_EMAIL}

    def test_phone_key_masked(self) -> None:
        assert redact_pii({"phone": "+1-555-0100"}) == {"phone": REDACTED_PHONE}

    @pytest.mark.parametrize(
        "key",
        ["email", "user_email", "contactEmail", "owner_email", "Actor_Email"],
    )
    def test_email_key_variants(self, key: str) -> None:
        assert redact_pii({key: "x@y.io"}) == {key: REDACTED_EMAIL}

    @pytest.mark.parametrize(
        "key",
        ["phone", "phone_number", "contactPhone", "tg_phone", "Telephone", "mobile"],
    )
    def test_phone_key_variants(self, key: str) -> None:
        assert redact_pii({key: "+1-202-555-0100"}) == {key: REDACTED_PHONE}

    def test_secret_keys_still_masked_with_stars(self) -> None:
        # Backward-compat: generic secret keys keep the "***" token, not PII tokens.
        assert redact_pii({"password": "hunter2"}) == {"password": "***"}
        assert redact_pii({"api_hash": "0" * 32}) == {"api_hash": "***"}


class TestRedactPiiPatternBased:
    def test_email_inside_freeform_string(self) -> None:
        out = redact_pii({"reason": "User alice@example.com asked for release"})
        assert "alice@example.com" not in out["reason"]
        assert REDACTED_EMAIL in out["reason"]

    @pytest.mark.parametrize(
        "phone",
        [
            "+7 (495) 123-45-67",
            "8-800-555-3535",
            "+1.555.012.3456",
            "+1 202 555 0100",
        ],
    )
    def test_phone_patterns_inside_freeform_string(self, phone: str) -> None:
        out = redact_pii({"reason": f"Contact {phone} for details"})
        assert phone not in out["reason"]
        assert REDACTED_PHONE in out["reason"]

    def test_short_digit_sequences_are_not_masked_as_phones(self) -> None:
        # 8 digits → not enough for a phone. Should remain intact.
        out = redact_pii({"note": "Reference id 12345678 in queue"})
        assert "12345678" in out["note"]
        assert REDACTED_PHONE not in out["note"]

    def test_iso_timestamp_left_alone(self) -> None:
        out = redact_pii({"observed_at": "2026-05-25T14:30:00"})
        assert out["observed_at"] == "2026-05-25T14:30:00"

    def test_uuid_not_masked_as_phone(self) -> None:
        out = redact_pii({"id": "550e8400-e29b-41d4-a716-446655440000"})
        assert out["id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_all_numeric_uuid_not_masked_as_phone(self) -> None:
        """Tightening of the dash-segmented phone heuristic: any group longer
        than 5 digits disqualifies a candidate as a phone number. This is
        what stops `00000000-0000-4000-8000-000000000001` (a deterministic
        UUID layout used in our test fixtures) being eaten by REDACTED_PHONE.
        """
        uuid_value = "00000000-0000-4000-8000-000000000001"
        out = redact_pii({"note": f"correlation {uuid_value} for trace"})
        assert uuid_value in out["note"]
        assert REDACTED_PHONE not in out["note"]

    def test_too_short_digit_run_not_masked(self) -> None:
        # 8 digits inside punctuation context fall short of the phone
        # min-digit threshold and exit the substitution unchanged.
        out = redact_pii({"note": "12345678"})
        assert out["note"] == "12345678"

    def test_regex_match_with_too_few_digits_is_not_masked(self) -> None:
        """`1.2.3.4.5` has 5 digits — the regex window matches because of
        the separator-heavy layout, but `_phone_substitution` early-exits
        via the digit-count guard so the value is preserved.
        """
        out = redact_pii({"note": "see 1.2.3.4.5 for details"})
        assert "1.2.3.4.5" in out["note"]
        assert REDACTED_PHONE not in out["note"]

    def test_recursive_tuple_container(self) -> None:
        # tuple containers must follow the same recursive masking as lists.
        out = redact_pii(("alice@example.com", "no-email-here"))
        assert out == [REDACTED_EMAIL, "no-email-here"]

    def test_multiple_pii_in_one_string(self) -> None:
        text = "alice@example.com and +1-202-555-0100 both leaked"
        out = redact_pii({"note": text})
        assert "alice@example.com" not in out["note"]
        assert "+1-202-555-0100" not in out["note"]
        assert out["note"].count(REDACTED_EMAIL) == 1
        assert out["note"].count(REDACTED_PHONE) == 1


class TestRedactPiiRecursive:
    def test_nested_dict_email(self) -> None:
        assert redact_pii({"actor": {"email": "x@y.z", "name": "Alice"}}) == {
            "actor": {"email": REDACTED_EMAIL, "name": "Alice"},
        }

    def test_list_under_email_keyed_field_collapses_to_token(self) -> None:
        # `emails` (plural) matches the email fragment so the whole value
        # collapses to the token — key-based masking wins over recursion.
        out = redact_pii({"emails": ["alice@example.com", "bob@example.com"]})
        assert out == {"emails": REDACTED_EMAIL}

    def test_list_under_generic_key_masks_each_string(self) -> None:
        out = redact_pii({"contacts": ["alice@example.com", "bob@example.com"]})
        assert out == {"contacts": [REDACTED_EMAIL, REDACTED_EMAIL]}

    def test_tuple_handled_like_list(self) -> None:
        out = redact_pii({"contacts": ("alice@example.com", "bob@example.com")})
        assert out == {"contacts": [REDACTED_EMAIL, REDACTED_EMAIL]}

    def test_non_string_non_container_passthrough(self) -> None:
        sample = {"count": 42, "ratio": 0.5, "active": True, "nothing": None}
        assert redact_pii(sample) == sample

    def test_empty_dict_passthrough(self) -> None:
        assert redact_pii({}) == {}

    def test_non_string_keys_preserved(self) -> None:
        assert redact_pii({42: "alice@example.com"}) == {42: REDACTED_EMAIL}


class TestRedactTextPiiPatterns:
    """Existing redact_text() callers (logs, journal, etc.) now also strip PII."""

    def test_redact_text_strips_email(self) -> None:
        assert REDACTED_EMAIL in redact_text("Contact alice@example.com today")

    def test_redact_text_strips_phone(self) -> None:
        assert REDACTED_PHONE in redact_text("Call +1-202-555-0100 now")

    def test_redact_text_preserves_safe_strings(self) -> None:
        assert redact_text("All good here") == "All good here"

    def test_redact_text_layers_secrets_and_pii(self) -> None:
        text = "password=hunter2 from alice@example.com"
        out = redact_text(text)
        assert "hunter2" not in out
        assert "alice@example.com" not in out
        assert REDACTED_EMAIL in out


class TestRecordSensitiveAuditEventIntegration:
    """End-to-end: stored DB metadata never carries plaintext PII (audit B F-001)."""

    def test_email_in_metadata_is_redacted_on_insert(self, db_session) -> None:
        from app.services.sensitive_audit import record_sensitive_audit_event

        event = record_sensitive_audit_event(
            db_session,
            workspace_id="ws-1",
            action="account.deleted",
            entity_type="account",
            entity_id="acc-1",
            metadata={"email": "test@example.com", "phone": "+1-555-0100"},
        )
        db_session.flush()

        assert event.metadata_json == {
            "email": REDACTED_EMAIL,
            "phone": REDACTED_PHONE,
        }

    def test_reason_freeform_pii_is_redacted_on_insert(self, db_session) -> None:
        from app.services.sensitive_audit import record_sensitive_audit_event

        event = record_sensitive_audit_event(
            db_session,
            workspace_id="ws-1",
            action="account.deleted",
            entity_type="account",
            entity_id="acc-1",
            reason="User test@example.com requested early release",
        )
        db_session.flush()

        assert event.reason is not None
        assert "test@example.com" not in event.reason
        assert REDACTED_EMAIL in event.reason

    def test_nested_metadata_redacted_end_to_end(self, db_session) -> None:
        from app.services.sensitive_audit import record_sensitive_audit_event

        event = record_sensitive_audit_event(
            db_session,
            workspace_id="ws-1",
            action="account.deleted",
            entity_type="account",
            entity_id="acc-1",
            metadata={
                "actor": {"email": "owner@example.com", "name": "Alice"},
                "history": ["call +1-202-555-0100", "no email recorded"],
                "credentials": {"access_token": "abc", "refresh_token": "def"},
            },
        )
        db_session.flush()

        assert event.metadata_json["actor"] == {
            "email": REDACTED_EMAIL,
            "name": "Alice",
        }
        # history[0] phone substring masked; history[1] left untouched
        assert REDACTED_PHONE in event.metadata_json["history"][0]
        assert event.metadata_json["history"][1] == "no email recorded"
        # secret keys still mask with "***" (no regression).
        assert event.metadata_json["credentials"] == {
            "access_token": "***",
            "refresh_token": "***",
        }
