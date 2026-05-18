from __future__ import annotations


def test_warmup_sessions_rejects_unbounded_page(app_client) -> None:
    response = app_client.get("/api/warmup/sessions", params={"page": 10001})

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"


def test_warmup_session_events_rejects_unbounded_page(app_client) -> None:
    response = app_client.get(
        "/api/warmup/sessions/00000000-0000-4000-8000-000000000001/events",
        params={"page": 10001},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
