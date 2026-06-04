from __future__ import annotations

import pytest

from app.modules.account_onboarding import tdlib_verification
from app.modules.account_onboarding.tdlib_verification import verify_imported_tdlib_session


class _FakeReadonlyAdapter:
    def __init__(self, result: dict[str, object]) -> None:
        self._result = result

    def check_account(self, account_id: str) -> dict[str, object]:
        assert account_id == "staging-account"
        return self._result


def _patch_readonly(monkeypatch: pytest.MonkeyPatch, result: dict[str, object]) -> None:
    monkeypatch.setattr(
        tdlib_verification,
        "build_tdlib_readonly_validity_adapter",
        lambda: _FakeReadonlyAdapter(result),
    )


def test_tdlib_import_verification_maps_ready_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_readonly(
        monkeypatch,
        {"status": "valid", "telegram_user_id": "42", "profile": {"username": "demo"}},
    )

    result = verify_imported_tdlib_session("staging-account", expected_telegram_user_id="42")

    assert result.outcome == "verified_ready"
    assert result.telegram_user_id == "42"
    assert result.profile == {"username": "demo"}


def test_tdlib_import_verification_rejects_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_readonly(monkeypatch, {"status": "valid", "telegram_user_id": "42"})

    result = verify_imported_tdlib_session("staging-account", expected_telegram_user_id="43")

    assert result.outcome == "identity_mismatch"
    assert result.error_code == "tdlib_identity_mismatch"


def test_tdlib_import_verification_maps_reauth(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_readonly(
        monkeypatch,
        {"status": "reauth_required", "error_code": "auth_key_unregistered"},
    )

    result = verify_imported_tdlib_session("staging-account")

    assert result.outcome == "requires_reauth"
    assert result.error_code == "auth_key_unregistered"


def test_tdlib_import_verification_maps_unavailable_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_readonly(
        monkeypatch,
        {"status": "runtime_broken", "error_code": "tdlib_readonly_runtime_broken"},
    )

    result = verify_imported_tdlib_session("staging-account")

    assert result.outcome == "tdlib_unavailable"
    assert result.error_code == "tdlib_readonly_runtime_broken"


def test_tdlib_import_verification_maps_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_readonly(
        monkeypatch,
        {"status": "unknown", "runtime_health": "timeout", "error_code": "tdlib_readonly_timeout"},
    )

    result = verify_imported_tdlib_session("staging-account")

    assert result.outcome == "verification_timeout"
    assert result.error_code == "tdlib_readonly_timeout"


def test_tdlib_import_verification_maps_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_readonly(
        monkeypatch,
        {"status": "runtime_broken", "error_code": "missing_tdlib_credentials"},
    )

    result = verify_imported_tdlib_session("staging-account")

    assert result.outcome == "tdlib_not_configured"
    assert result.error_code == "missing_tdlib_credentials"
