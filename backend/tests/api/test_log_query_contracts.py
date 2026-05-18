from __future__ import annotations


def test_operation_logs_reject_unknown_query_params(app_client) -> None:
    response = app_client.get("/api/operation-logs", params={"offset": 0, "unknown": "1"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "HTTP_ERROR"


def test_audit_events_reject_unknown_query_params(app_client) -> None:
    response = app_client.get("/api/audit/events", params={"offset": 0, "unknown": "1"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "HTTP_ERROR"
