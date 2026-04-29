from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_utils import log_error, log_warn


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        error_class: str,
        message: str,
        details: dict[str, Any] | None = None,
        field_errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_class = error_class
        self.message = message
        self.details = details
        self.field_errors = field_errors or []


def error_response(
    *,
    status_code: int,
    error_code: str,
    error_class: str,
    message: str,
    details: dict[str, Any] | None = None,
    field_errors: list[dict[str, str]] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    rid = request_id or str(uuid.uuid4())
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "error_class": error_class,
            "message": message,
            "details": details,
            "field_errors": field_errors or [],
            "request_id": rid,
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    log_fn = log_error if exc.status_code >= 500 else log_warn
    log_fn(
        "app_error",
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=exc.message,
        status=exc.status_code,
        path=request.url.path,
        request_id=request_id,
    )
    return error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=exc.message,
        details=exc.details,
        field_errors=exc.field_errors,
        request_id=request_id,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)

    if isinstance(exc.detail, dict) and {"error_code", "error_class", "message"} <= set(exc.detail.keys()):
        log_warn(
            "http_error",
            error_code=exc.detail["error_code"],
            message=exc.detail["message"],
            status=exc.status_code,
            path=request.url.path,
            request_id=request_id,
        )
        return error_response(
            status_code=exc.status_code,
            error_code=exc.detail["error_code"],
            error_class=exc.detail["error_class"],
            message=exc.detail["message"],
            details=exc.detail.get("details"),
            field_errors=exc.detail.get("field_errors", []),
            request_id=request_id,
        )

    error_code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    error_class = "not_found" if exc.status_code == 404 else "http_error"
    log_warn(
        "http_error",
        error_code=error_code,
        message=str(exc.detail),
        status=exc.status_code,
        path=request.url.path,
        request_id=request_id,
    )
    return error_response(
        status_code=exc.status_code,
        error_code=error_code,
        error_class=error_class,
        message=str(exc.detail),
        request_id=request_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    field_errors = []
    for error in exc.errors():
        location = [str(item) for item in error["loc"] if item != "body"]
        field_errors.append(
            {
                "field": ".".join(location) or "body",
                "message": error["msg"],
            }
        )

    log_warn(
        "validation_error",
        fields=[fe["field"] for fe in field_errors],
        path=request.url.path,
        request_id=request_id,
    )
    return error_response(
        status_code=422,
        error_code="REQUEST_VALIDATION_ERROR",
        error_class="validation",
        message="request validation failed",
        details={"errors": exc.errors()},
        field_errors=field_errors,
        request_id=request_id,
    )
