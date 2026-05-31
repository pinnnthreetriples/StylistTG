from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse, urlunparse


SECRET_FRAGMENTS = ("password", "secret", "token", "key", "jwt")


def _empty_details() -> dict[str, Any]:
    return {}


def _empty_results() -> list[CheckResult]:
    return []


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=_empty_details)


@dataclass
class CheckReport:
    name: str
    results: list[CheckResult] = field(default_factory=_empty_results)
    started_at: float = field(default_factory=time.time)

    def add(self, name: str, status: str, message: str, **details: Any) -> None:
        self.results.append(CheckResult(name=name, status=status, message=message, details=details))

    @property
    def has_errors(self) -> bool:
        return any(item.status == "FAIL" for item in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_seconds": round(time.time() - self.started_at, 3),
            "status": "FAIL" if self.has_errors else "PASS",
            "results": [asdict(item) for item in self.results],
        }


def env_value(name: str, env: dict[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    value = source.get(name)
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def bool_env(name: str, env: dict[str, str] | None = None, *, default: bool = False) -> bool:
    value = env_value(name, env)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def int_env(name: str, env: dict[str, str] | None = None, *, default: int) -> int:
    value = env_value(name, env)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def sanitized_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return "<invalid-url>"
    host = parsed.hostname or parsed.netloc
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path if parsed.scheme.startswith("postgres") else ""
    return urlunparse((parsed.scheme, f"{host}{port}", path, "", "", ""))


def url_host(value: str | None) -> str:
    if not value:
        return ""
    return urlparse(value).hostname or ""


def redact_value(name: str, value: Any) -> Any:
    normalized = name.lower().replace("-", "_")
    if any(fragment in normalized for fragment in SECRET_FRAGMENTS):
        return "<redacted>"
    if isinstance(value, str) and "://" in value:
        return sanitized_url(value)
    return value


def render_report(report: CheckReport, *, json_output: bool) -> str:
    payload = report.to_dict()
    if json_output:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [f"{payload['name']}: {payload['status']} ({payload['duration_seconds']}s)"]
    for item in report.results:
        details = " ".join(
            f"{key}={redact_value(key, value)}" for key, value in item.details.items()
        )
        suffix = f" [{details}]" if details else ""
        lines.append(f"{item.status:4} {item.name}: {item.message}{suffix}")
    return "\n".join(lines)


def print_and_exit(report: CheckReport, *, json_output: bool) -> None:
    print(render_report(report, json_output=json_output))
    raise SystemExit(1 if report.has_errors else 0)


def add_common_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Output JSON without secrets.")


def is_cloud_env(env: dict[str, str] | None = None) -> bool:
    app_env = env_value("APP_ENV", env) or "local"
    db_mode = env_value("DB_CONNECTION_MODE", env) or "local"
    return app_env in {"staging", "production"} or db_mode == "neon"


def require_not_production(
    report: CheckReport, *, allow_production: bool, env: dict[str, str] | None = None
) -> bool:
    app_env = env_value("APP_ENV", env) or "local"
    if app_env == "production" and not allow_production:
        report.add(
            "production_guard", "FAIL", "Refusing production smoke without --allow-production"
        )
        return False
    return True


def looks_production(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in ("prod", "production", "live"))


def safe_smoke_prefix(prefix: str) -> str:
    normalized = prefix.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts or parts[0] != "smoke" or ".." in parts:
        raise ValueError("smoke prefix must stay under smoke/")
    return "/".join(parts) + "/"


def main_guard(fn: Callable[[], None]) -> None:
    try:
        fn()
    except KeyboardInterrupt:
        # SIGINT (130) — surface the interrupt to the operator and exit cleanly.
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130) from None
