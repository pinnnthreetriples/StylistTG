from __future__ import annotations

import argparse
import os
import subprocess
import time

from sqlalchemy import create_engine, text

from app.scripts.common import (
    CheckReport,
    add_common_json_arg,
    env_value,
    looks_production,
    main_guard,
    print_and_exit,
    require_not_production,
    sanitized_url,
)


def run_neon_smoke(
    *,
    check_runtime: bool = False,
    check_migrations: bool = False,
    upgrade_head: bool = False,
    readonly: bool = False,
    allow_production: bool = False,
    env: dict[str, str] | None = None,
    engine_factory=create_engine,
    command_runner=subprocess.run,
) -> CheckReport:
    report = CheckReport("neon_smoke")
    if not require_not_production(report, allow_production=allow_production, env=env):
        return report
    runtime_url = env_value("DATABASE_RUNTIME_URL", env) or env_value("DATABASE_URL", env)
    direct_url = env_value("DATABASE_DIRECT_URL", env)
    app_env = env_value("APP_ENV", env) or "local"
    for label, url in (("runtime", runtime_url), ("direct", direct_url)):
        if looks_production(url) and app_env != "production":
            report.add(f"{label}_guard", "FAIL", "Production-looking database URL outside production", url=sanitized_url(url))
    if check_runtime or readonly:
        if not runtime_url:
            report.add("runtime_url", "FAIL", "DATABASE_RUNTIME_URL or DATABASE_URL is required")
        else:
            _check_db(report, "runtime", runtime_url, engine_factory=engine_factory)
    if check_migrations or upgrade_head:
        if not direct_url:
            report.add("direct_url", "FAIL", "DATABASE_DIRECT_URL is required")
        else:
            _check_db(report, "direct", direct_url, engine_factory=engine_factory)
            _check_alembic(report, direct_url, upgrade_head=upgrade_head, command_runner=command_runner)
    return report


def _check_db(report: CheckReport, label: str, url: str, *, engine_factory) -> None:
    started = time.time()
    engine = engine_factory(url)
    try:
        with engine.connect() as connection:
            row = connection.execute(text("select current_database(), current_user")).one()
        report.add(f"{label}_connect", "PASS", "Database connection succeeded", url=sanitized_url(url), database=row[0], user=row[1], duration_seconds=round(time.time() - started, 3))
    except Exception as exc:
        report.add(f"{label}_connect", "FAIL", "Database connection failed", url=sanitized_url(url), error=type(exc).__name__)
    finally:
        dispose = getattr(engine, "dispose", None)
        if callable(dispose):
            dispose()


def _check_alembic(report: CheckReport, direct_url: str, *, upgrade_head: bool, command_runner) -> None:
    command = ["python", "-m", "alembic", "upgrade" if upgrade_head else "current", "head" if upgrade_head else ""]
    command = [part for part in command if part]
    command_env = os.environ.copy()
    command_env["DATABASE_URL"] = direct_url
    command_env["DATABASE_DIRECT_URL"] = direct_url
    try:
        result = command_runner(command, env=command_env, text=True, capture_output=True, check=False)
    except Exception as exc:
        report.add("alembic", "FAIL", "Alembic command failed to start", error=type(exc).__name__)
        return
    status = "PASS" if getattr(result, "returncode", 1) == 0 else "FAIL"
    report.add("alembic", status, "Alembic upgrade head completed" if upgrade_head else "Alembic current completed", returncode=getattr(result, "returncode", None))


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Neon dev/staging smoke checks.")
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--check-migrations", action="store_true")
    parser.add_argument("--upgrade-head", action="store_true")
    parser.add_argument("--readonly", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    add_common_json_arg(parser)
    args = parser.parse_args()
    if not any((args.check_runtime, args.check_migrations, args.upgrade_head, args.readonly)):
        args.readonly = True
    report = run_neon_smoke(
        check_runtime=args.check_runtime,
        check_migrations=args.check_migrations,
        upgrade_head=args.upgrade_head,
        readonly=args.readonly,
        allow_production=args.allow_production,
    )
    print_and_exit(report, json_output=args.json)


if __name__ == "__main__":
    main_guard(main)
