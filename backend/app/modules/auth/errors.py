from __future__ import annotations

from app.errors import AppError


def auth_required() -> AppError:
    return AppError(
        status_code=401,
        error_code="AUTH_REQUIRED",
        error_class="auth_required",
        message="authorization bearer token is required",
    )


def workspace_access_denied() -> AppError:
    return AppError(
        status_code=403,
        error_code="WORKSPACE_ACCESS_DENIED",
        error_class="forbidden",
        message="workspace access denied",
    )


def user_disabled() -> AppError:
    return AppError(
        status_code=403,
        error_code="USER_DISABLED",
        error_class="forbidden",
        message="user is disabled",
    )


def workspace_disabled() -> AppError:
    return AppError(
        status_code=403,
        error_code="WORKSPACE_DISABLED",
        error_class="forbidden",
        message="workspace is disabled",
    )


def role_invalid() -> AppError:
    return AppError(
        status_code=403,
        error_code="ROLE_INVALID",
        error_class="forbidden",
        message="workspace role is invalid",
    )


def role_forbidden() -> AppError:
    return AppError(
        status_code=403,
        error_code="ROLE_FORBIDDEN",
        error_class="forbidden",
        message="insufficient workspace role",
    )


def auth_mode_unsupported() -> AppError:
    return AppError(
        status_code=500,
        error_code="AUTH_MODE_UNSUPPORTED",
        error_class="configuration",
        message="auth mode is unsupported",
    )


__all__ = [
    "auth_mode_unsupported",
    "auth_required",
    "role_forbidden",
    "role_invalid",
    "user_disabled",
    "workspace_access_denied",
    "workspace_disabled",
]
