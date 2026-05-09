from __future__ import annotations


def phone_hint(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"


def required_phone_hint(value: object) -> str:
    return phone_hint(value) or "***"
