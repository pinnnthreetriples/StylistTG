import asyncio
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.auth_batches import router as auth_batches_router
from app.api.account_update import router as account_update_router
from app.api.account_imports import router as account_imports_router
from app.api.accounts import router as accounts_router
from app.api.audit import router as audit_router
from app.api.assets import router as assets_router
from app.api.dashboard import router as dashboard_router
from app.api.diagnostics import router as diagnostics_router
from app.api.jobs import router as jobs_router
from app.api.me import router as me_router
from app.api.operation_logs import router as operation_logs_router
from app.api.settings import router as settings_router
from app.api.story_drafts import router as story_drafts_router
from app.api.story_capabilities import router as story_capabilities_router
from app.api.story_posts import router as story_posts_router
from app.api.telegram_auth import router as telegram_auth_router
from app.api.tdlib_runtime import router as tdlib_runtime_router
from app.api.warmup import router as warmup_router
from app.api.workers import router as workers_router
from app.config import settings
from app.db import SessionLocal
from app.errors import app_error_handler, http_exception_handler, validation_exception_handler, AppError
from app.logging_utils import configure_logging, generate_request_id, log_event, log_request
from app.schemas import DiagnosticsRead
from app.services.auth_batch_recovery import recover_auth_batches
from app.services.runtime_diagnostics import build_runtime_diagnostics
from app.services.stale_jobs import reap_stale_jobs

configure_logging(log_dir=settings.storage_root.parent / "logs")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    reaper_task: asyncio.Task[None] | None = None
    if settings.stale_job_reaper_enabled:
        reaper_task = asyncio.create_task(_stale_job_reaper_loop())
    try:
        yield
    finally:
        if reaper_task is not None:
            reaper_task.cancel()
            with suppress(asyncio.CancelledError):
                await reaper_task


async def _stale_job_reaper_loop() -> None:
    interval_seconds = max(1, settings.stale_job_reaper_interval_seconds)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            with SessionLocal() as session:
                reaped = reap_stale_jobs(session, stale_after_seconds=settings.stale_job_timeout_seconds)
                recovered_auth_batches = recover_auth_batches(session)
            if reaped:
                log_event("stale_job_reaper_reaped", count=reaped)
            if recovered_auth_batches:
                log_event("auth_batch_recovery_recovered", count=recovered_auth_batches)
        except Exception as exc:
            log_event(
                "stale_job_reaper_error",
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
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(account_update_router)
app.include_router(account_imports_router)
app.include_router(auth_router)
app.include_router(auth_batches_router)
app.include_router(accounts_router)
app.include_router(audit_router)
app.include_router(assets_router)
app.include_router(dashboard_router)
app.include_router(diagnostics_router)
app.include_router(jobs_router)
app.include_router(me_router)
app.include_router(operation_logs_router)
app.include_router(settings_router)
app.include_router(story_drafts_router)
app.include_router(story_capabilities_router)
app.include_router(story_posts_router)
app.include_router(telegram_auth_router)
app.include_router(tdlib_runtime_router)
app.include_router(warmup_router)
app.include_router(workers_router)


@app.middleware("http")
async def operator_guard_middleware(request: Request, call_next):
    if request.url.path in {"/health", "/ready", "/diagnostics/runtime"}:
        return await call_next(request)
    if settings.enforce_localhost_only and not _is_local_client(request):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "operator API is available only from localhost"},
        )
    if settings.operator_api_token and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("X-Operator-Token") != settings.operator_api_token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "operator token is required"},
            )
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = generate_request_id()
    request.state.request_id = request_id
    start = time.perf_counter()

    response: Response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    # Skip noisy health/ready polls
    if request.url.path not in ("/health", "/ready"):
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

    response.headers["X-Request-ID"] = request_id
    return response


def _is_local_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host.startswith("::ffff:"):
        host = host.removeprefix("::ffff:")
    allowed = {item.strip() for item in settings.operator_allowed_client_hosts.split(",") if item.strip()}
    return host in allowed


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=DiagnosticsRead)
def ready(response: Response):
    diagnostics = DiagnosticsRead(**build_runtime_diagnostics())
    if diagnostics.database != "ok" or diagnostics.redis != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return diagnostics
