from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.scripts.cloud_config_check import validate_cloud_config
from app.scripts.common import CheckReport, add_common_json_arg, main_guard, print_and_exit
from app.scripts.neon_smoke import run_neon_smoke
from app.scripts.object_storage_smoke import run_object_storage_smoke
from app.scripts.redis_smoke import run_redis_smoke
from app.scripts.supabase_auth_smoke import run_supabase_auth_smoke

HttpFetcher = Callable[[str, float], tuple[int, Any]]


def run_staging_smoke(
    *,
    base_url: str | None = None,
    env: dict[str, str] | None = None,
    include_storage: bool = False,
    allow_write_cloud: bool = False,
    allow_production: bool = False,
    http_fetcher: HttpFetcher | None = None,
    cloud_config_runner=validate_cloud_config,
    neon_runner=run_neon_smoke,
    supabase_runner=run_supabase_auth_smoke,
    redis_runner=run_redis_smoke,
    storage_runner=run_object_storage_smoke,
) -> CheckReport:
    effective_env = dict(env) if env is not None else os.environ.copy()
    report = CheckReport("staging_smoke")

    if base_url:
        fetcher = http_fetcher or _http_get_json
        _check_endpoint(report, "health_endpoint", base_url, "health", fetcher)
        _check_endpoint(report, "ready_endpoint", base_url, "ready", fetcher)
        _check_endpoint(report, "runtime_diagnostics_endpoint", base_url, "diagnostics/runtime", fetcher)

    for child in (
        cloud_config_runner(effective_env),
        neon_runner(
            readonly=True,
            check_migrations=True,
            upgrade_head=False,
            allow_production=allow_production,
            env=effective_env,
        ),
        supabase_runner(env=effective_env),
        redis_runner(allow_production=allow_production, env=effective_env),
    ):
        _extend(report, child)

    if include_storage:
        _extend(
            report,
            storage_runner(
                allow_write_cloud=allow_write_cloud,
                allow_production=allow_production,
                env=effective_env,
            ),
        )
    return report


def load_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _check_endpoint(
    report: CheckReport,
    name: str,
    base_url: str,
    path: str,
    fetcher: HttpFetcher,
) -> None:
    url = urljoin(base_url.rstrip("/") + "/", path)
    try:
        status_code, payload = fetcher(url, 5.0)
    except Exception as exc:
        report.add(name, "FAIL", f"{path} endpoint request failed", url=url, error=type(exc).__name__)
        return
    if status_code != 200:
        report.add(name, "FAIL", f"{path} endpoint returned non-200 status", url=url, status_code=status_code)
        return
    report.add(name, "PASS", f"{path} endpoint returned 200", url=url, payload_status=_payload_status(payload))


def _http_get_json(url: str, timeout: float) -> tuple[int, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        return exc.code, None
    except URLError:
        raise


def _payload_status(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("status")
        return str(value) if value is not None else None
    return None


def _extend(report: CheckReport, child) -> None:
    for result in child.results:
        report.results.append(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe staging backend/worker smoke orchestrator.")
    parser.add_argument("--base-url", help="Staging backend base URL for /health and /ready checks.")
    parser.add_argument("--env-file", type=Path, help="Ignored local env file to overlay for smoke checks.")
    parser.add_argument("--include-storage", action="store_true", help="Include object storage dry-run/write check.")
    parser.add_argument("--allow-write-cloud", action="store_true", help="Allow object storage write/read/delete smoke.")
    parser.add_argument("--allow-production", action="store_true", help="Allow production-looking smoke targets.")
    add_common_json_arg(parser)
    args = parser.parse_args()
    env = load_env_file(args.env_file) if args.env_file else None
    print_and_exit(
        run_staging_smoke(
            base_url=args.base_url,
            env=env,
            include_storage=args.include_storage,
            allow_write_cloud=args.allow_write_cloud,
            allow_production=args.allow_production,
        ),
        json_output=args.json,
    )


if __name__ == "__main__":
    main_guard(main)
