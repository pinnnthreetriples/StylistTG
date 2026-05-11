from __future__ import annotations

import asyncio
import json

from fastapi.exceptions import RequestValidationError

from app.errors import validation_exception_handler


class _Request:
    class _State:
        request_id = "test-request"

    class _Url:
        path = "/api/auth-batches/validate-phones"

    state = _State()
    url = _Url()


def test_validation_error_response_redacts_non_json_body() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "model_attributes_type",
                "loc": ("body",),
                "msg": "Input should be a valid dictionary",
                "input": b'{"password":"secret"}',
            }
        ],
        body=b'{"password":"secret"}',
    )

    response = asyncio.run(validation_exception_handler(_Request(), exc))  # type: ignore[arg-type]

    assert response.status_code == 422
    payload = json.loads(response.body)
    assert payload["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert payload["details"]["errors"][0]["input"] == "[redacted]"
    assert "secret" not in response.body.decode()
