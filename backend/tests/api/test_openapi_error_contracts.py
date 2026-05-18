from __future__ import annotations

from app.main import app


def test_static_api_paths_return_method_not_allowed_before_dynamic_fallback(app_client) -> None:
    response = app_client.delete("/api/accounts/jobs")

    assert response.status_code == 405
    assert response.json()["detail"] == "Method Not Allowed"


def test_resource_endpoints_document_not_found_error_response() -> None:
    schema = app.openapi()

    for method, path in (
        ("post", "/api/account-update/preview"),
        ("get", "/api/accounts/{account_id}/audit-events"),
        ("put", "/api/warmup/sessions/{session_id}/pause"),
    ):
        response = schema["paths"][path][method]["responses"]["404"]

        assert response["description"] == "Not Found"
        assert (
            response["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/ApiErrorRead"
        )


def test_body_endpoints_document_bad_request_response() -> None:
    schema = app.openapi()

    response = schema["paths"]["/api/account-import-batches"]["post"]["responses"]["400"]

    assert response["description"] == "Bad Request"
    assert response["content"]["application/json"]["schema"] == {"type": "object"}


def test_ready_documents_unavailable_response() -> None:
    schema = app.openapi()

    response = schema["paths"]["/ready"]["get"]["responses"]["503"]

    assert response["description"] == "Service Unavailable"
    assert (
        response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ReadinessRead"
    )


def test_optional_query_parameters_are_optional_not_nullable() -> None:
    schema = app.openapi()

    parameters = schema["paths"]["/api/auth-batches/{batch_id}/poll"]["get"]["parameters"]
    updated_since = next(item for item in parameters if item["name"] == "updated_since")

    assert updated_since["required"] is False
    assert updated_since["schema"]["type"] == "string"
    assert updated_since["schema"]["format"] == "date-time"
    assert "anyOf" not in updated_since["schema"]


def test_conflict_response_is_documented() -> None:
    schema = app.openapi()

    response = schema["paths"]["/api/accounts"]["post"]["responses"]["409"]

    assert response["description"] == "Conflict"
    assert (
        response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ApiErrorRead"
    )


def test_idempotent_create_response_is_documented() -> None:
    schema = app.openapi()

    response = schema["paths"]["/api/auth-batches"]["post"]["responses"]["200"]

    assert response["description"] == "OK"
    assert (
        response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/AuthBatchSnapshotRead"
    )
