from __future__ import annotations

from app.services.auth_context import get_current_auth_context


def test_supabase_auth_context_requires_bearer_token(db_session, monkeypatch) -> None:
    class DummyRequest:
        headers: dict[str, str] = {}

    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")

    try:
        get_current_auth_context(DummyRequest(), db_session)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        code = getattr(exc, "error_code", "")
    else:
        status_code = None
        code = ""

    assert status_code == 401
    assert code == "AUTH_REQUIRED"
