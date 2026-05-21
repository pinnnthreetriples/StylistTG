import asyncio
from copy import deepcopy
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, suppress
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from starlette.types import ExceptionHandler

from app.api.auth import router as auth_router
from app.api.auth_batches import router as auth_batches_router
from app.api.account_imports import router as account_imports_router
from app.api.account_audit_routes import router as account_audit_router
from app.api.account_compat_routes import router as account_compat_router
from app.api.account_jobs_routes import router as account_jobs_router
from app.api.account_lifecycle_routes import router as account_lifecycle_router
from app.api.account_proxy_routes import router as account_proxy_router
from app.api.account_runtime_routes import router as account_runtime_router
from app.api.account_ggr_routes import router as account_ggr_router
from app.api.account_profile_completeness_routes import (
    router as account_profile_completeness_router,
)
from app.api.account_quarantine_routes import router as account_quarantine_router
from app.api.account_status_routes import router as account_status_router
from app.api.bought_onboarding_routes import router as bought_onboarding_router
from app.api.human_behavior_routes import router as human_behavior_router
from app.api.account_safety_routes import router as account_safety_router
from app.api.accounts import router as accounts_router
from app.api.audit import router as audit_router
from app.api.assets import router as assets_router
from app.api.dashboard import router as dashboard_router
from app.api.diagnostics import router as diagnostics_router
from app.api.jobs import router as jobs_router
from app.api.me import router as me_router
from app.api.neuro_commenting import router as neuro_commenting_router
from app.api.operation_logs import router as operation_logs_router
from app.api.safety_policy import router as safety_policy_router
from app.api.settings import router as settings_router
from app.api.story_drafts import router as story_drafts_router
from app.api.story_capabilities import router as story_capabilities_router
from app.api.story_posts import router as story_posts_router
from app.api.telegram_auth import router as telegram_auth_router
from app.api.tdlib_runtime import router as tdlib_runtime_router
from app.api.workspace_feature_flags_routes import router as workspace_feature_flags_router
from app.api.workers import router as workers_router
from app.config import settings
from app.db import SessionLocal
from app.errors import (
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
    AppError,
)
from app.logging_utils import configure_logging, generate_request_id, log_event, log_request
from app.modules.registry import iter_routers
from app.observability import init_api_observability
from app.schemas import ApiErrorRead, ReadinessRead
from app.services.auth_batch_recovery import recover_auth_batches
from app.services.runtime_diagnostics import build_runtime_diagnostics
from app.services.stale_jobs import reap_stale_jobs

configure_logging(
    log_dir=settings.storage_root.parent / "logs",
    log_to_file=settings.log_to_file,
    betterstack_source_token=(
        settings.betterstack_source_token.get_secret_value()
        if settings.betterstack_source_token
        else None
    ),
    betterstack_ingesting_host=settings.betterstack_ingesting_host,
    betterstack_request_timeout_seconds=settings.betterstack_request_timeout_seconds,
)
init_api_observability()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    reaper_task: asyncio.Task[None] | None = None
    warmup_ticker_task: asyncio.Task[None] | None = None
    if settings.stale_job_reaper_enabled:
        reaper_task = asyncio.create_task(_stale_job_reaper_loop())
    if settings.warmup_scheduler_enabled and settings.warmup_workers_enabled:
        warmup_ticker_task = asyncio.create_task(_warmup_scheduler_loop())
    try:
        yield
    finally:
        for task in (reaper_task, warmup_ticker_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


def _reap_stale_sync() -> tuple[int, int]:
    """Run stale-job reaping and auth-batch recovery in a synchronous context."""
    with SessionLocal() as session:
        reaped = reap_stale_jobs(session, stale_after_seconds=settings.stale_job_timeout_seconds)
        recovered = recover_auth_batches(session)
    return reaped, recovered


async def _stale_job_reaper_loop() -> None:
    interval_seconds = max(1, settings.stale_job_reaper_interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            reaped, recovered_auth_batches = await asyncio.to_thread(_reap_stale_sync)
            if reaped:
                log_event("stale_job_reaper_reaped", count=reaped)
            if recovered_auth_batches:
                log_event("auth_batch_recovery_recovered", count=recovered_auth_batches)
        except Exception as exc:
            log_event(
                "stale_job_reaper_error",
                error_class=exc.__class__.__name__,
            )


def _warmup_tick_sync() -> tuple[bool, bool | None]:
    """Execute warmup enqueue calls synchronously (Redis + rq are blocking)."""
    from app.job_queue.rq import (
        enqueue_warmup_dispatch_tick,
        enqueue_warmup_due_sessions,
    )

    enqueued = enqueue_warmup_due_sessions()
    dispatch_enqueued = enqueue_warmup_dispatch_tick()
    return enqueued, dispatch_enqueued


async def _warmup_scheduler_loop() -> None:
    """Periodic ticker that asks the warmup worker to scan for due sessions.

    Сам решение «какую сессию запустить» принимает воркер; тикер только
    рассылает безопасный enqueue (`unique=True`) с фиксированным `job_id`
    — повторные тики не плодят дубликаты в Redis. Hard kill-switch:
    `WARMUP_HARD_DISABLE=true` глушит цикл даже при включённом флаге
    `warmup_scheduler_enabled`.
    """
    interval_seconds = max(1, settings.warmup_scheduler_tick_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        if settings.warmup_hard_disable:
            continue
        if not settings.warmup_workers_enabled:
            continue
        try:
            enqueued, dispatch_enqueued = await asyncio.to_thread(_warmup_tick_sync)
            log_event("warmup_scheduler_tick", outcome="enqueued" if enqueued else "skipped")
            if dispatch_enqueued is not None:
                log_event(
                    "warmup_dispatch_tick",
                    outcome="enqueued" if dispatch_enqueued else "skipped",
                )
        except Exception as exc:
            log_event(
                "warmup_scheduler_error",
                error_class=exc.__class__.__name__,
            )


def _configured_cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]


app = FastAPI(title="StylistTG API", lifespan=lifespan)
if _configured_cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_configured_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_exception_handler(AppError, cast(ExceptionHandler, app_error_handler))
app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
app.add_exception_handler(
    RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
)
app.include_router(account_imports_router)
app.include_router(auth_router)
app.include_router(auth_batches_router)
app.include_router(account_safety_router)
app.include_router(account_proxy_router)
app.include_router(account_ggr_router)
app.include_router(account_profile_completeness_router)
app.include_router(account_quarantine_router)
app.include_router(account_status_router)
app.include_router(bought_onboarding_router)
app.include_router(human_behavior_router)
app.include_router(account_compat_router)
app.include_router(accounts_router)
app.include_router(account_lifecycle_router)
app.include_router(account_runtime_router)
app.include_router(account_jobs_router)
app.include_router(account_audit_router)
app.include_router(audit_router)
app.include_router(assets_router)
app.include_router(dashboard_router)
app.include_router(diagnostics_router)
app.include_router(jobs_router)
app.include_router(me_router)
app.include_router(neuro_commenting_router)
app.include_router(operation_logs_router)
app.include_router(safety_policy_router)
app.include_router(settings_router)
app.include_router(story_drafts_router)
app.include_router(story_capabilities_router)
app.include_router(story_posts_router)
app.include_router(telegram_auth_router)
app.include_router(tdlib_runtime_router)
app.include_router(workspace_feature_flags_router)
app.include_router(workers_router)
for module_router in iter_routers():
    app.include_router(module_router)


_static_route_methods_cache: dict[str, set[str]] | None = None


def _static_route_methods() -> dict[str, set[str]]:
    global _static_route_methods_cache
    if _static_route_methods_cache is not None:
        return _static_route_methods_cache

    route_methods: dict[str, set[str]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute) or "{" in route.path_format:
            continue
        methods = set(route.methods or set())
        if "GET" in methods:
            methods.add("HEAD")
        route_methods.setdefault(route.path_format, set()).update(methods)
    _static_route_methods_cache = route_methods
    return route_methods


def _api_error_schema_components() -> dict[str, Any]:
    schema = ApiErrorRead.model_json_schema(ref_template="#/components/schemas/{model}")
    defs = cast(dict[str, Any], schema.pop("$defs", {}))
    return {**defs, "ApiErrorRead": schema}


def _iter_openapi_operations(openapi_schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    paths = cast(dict[str, Any], openapi_schema.get("paths", {}))
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        path_item_dict = cast(dict[str, Any], path_item)
        for raw_operation in path_item_dict.values():
            if not isinstance(raw_operation, dict):
                continue
            yield cast(dict[str, Any], raw_operation)


def _document_standard_error_responses(openapi_schema: dict[str, Any]) -> None:
    components = cast(dict[str, Any], openapi_schema.setdefault("components", {}))
    schemas = cast(dict[str, Any], components.setdefault("schemas", {}))
    schemas.update(_api_error_schema_components())
    bad_request_response = {
        "description": "Bad Request",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
    not_found_response = {
        "description": "Not Found",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorRead"}}},
    }
    conflict_response = {
        "description": "Conflict",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorRead"}}},
    }
    for operation in _iter_openapi_operations(openapi_schema):
        if "responses" not in operation:
            continue
        responses = cast(dict[str, Any], operation["responses"])
        responses.setdefault("400", deepcopy(bad_request_response))
        responses.setdefault("404", deepcopy(not_found_response))
        responses.setdefault("409", deepcopy(conflict_response))


def _strip_query_parameter_nullability(openapi_schema: dict[str, Any]) -> None:
    for operation in _iter_openapi_operations(openapi_schema):
        parameters = operation.get("parameters", [])
        if not isinstance(parameters, list):
            continue
        for raw_parameter in cast(list[Any], parameters):
            if not isinstance(raw_parameter, dict):
                continue
            parameter = cast(dict[str, Any], raw_parameter)
            if parameter.get("in") != "query":
                continue
            schema = parameter.get("schema")
            if isinstance(schema, dict):
                _remove_null_schema_variant(cast(dict[str, Any], schema))


def _remove_null_schema_variant(schema: dict[str, Any]) -> None:
    any_of = schema.get("anyOf")
    if not isinstance(any_of, list):
        return
    any_of_variants = cast(list[Any], any_of)
    non_null_variants: list[Any] = [
        variant for variant in any_of_variants if not _is_null_schema_variant(variant)
    ]
    if len(non_null_variants) == 1 and isinstance(non_null_variants[0], dict):
        schema.pop("anyOf")
        schema.update(cast(dict[str, Any], non_null_variants[0]))
    elif len(non_null_variants) != len(any_of_variants):
        schema["anyOf"] = non_null_variants


def _is_null_schema_variant(variant: Any) -> bool:
    if not isinstance(variant, dict):
        return False
    return cast(dict[str, Any], variant).get("type") == "null"


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    _document_standard_error_responses(openapi_schema)
    _strip_query_parameter_nullability(openapi_schema)
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi


@app.middleware("http")
async def static_route_method_guard_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    allowed_methods = _static_route_methods().get(request.url.path)
    if allowed_methods is not None and request.method not in allowed_methods:
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={"detail": "Method Not Allowed"},
            headers={"Allow": ", ".join(sorted(allowed_methods))},
        )
    return await call_next(request)


@app.middleware("http")
async def operator_guard_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path in {"/health", "/ready"}:
        return await call_next(request)
    if settings.enforce_localhost_only and not _is_local_client(request):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "operator API is available only from localhost"},
        )
    if (
        settings.auth_mode == "local"
        and settings.operator_api_token
        and request.method not in {"GET", "HEAD", "OPTIONS"}
    ):
        if request.headers.get("X-Operator-Token") != settings.operator_api_token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "operator token is required"},
            )
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = generate_request_id()
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    # Skip noisy health/ready polls
    if request.url.path not in ("/health", "/ready"):
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=cast(Any, response.status_code),
            duration_ms=duration_ms,
            request_id=request_id,
        )

    response.headers["X-Request-ID"] = request_id
    return response


def _is_local_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host.startswith("::ffff:"):
        host = host.removeprefix("::ffff:")
    allowed = {
        item.strip() for item in settings.operator_allowed_client_hosts.split(",") if item.strip()
    }
    return host in allowed


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/ready",
    response_model=ReadinessRead,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service Unavailable",
            "model": ReadinessRead,
        }
    },
)
def ready(response: Response) -> ReadinessRead:
    diagnostics = build_runtime_diagnostics()
    is_ready = diagnostics.get("database") == "ok" and diagnostics.get("redis") == "ok"
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessRead(status="ok" if is_ready else "unavailable")
