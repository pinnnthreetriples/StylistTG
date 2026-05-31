from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any, Protocol, cast
from urllib.request import urlopen

from app.config import Settings
from app.errors import AppError
from app.scripts.common import (
    CheckReport,
    add_common_json_arg,
    env_value,
    main_guard,
    print_and_exit,
    sanitized_url,
)
from app.services.supabase_jwt import SupabaseJwtVerifier, clear_jwks_cache


JsonPayload = dict[str, Any]
JwksFetcher = Callable[[str], JsonPayload]


class JwtVerifier(Protocol):
    def verify(self, token: str) -> JsonPayload: ...


VerifierFactory = Callable[[Settings], JwtVerifier]


def run_supabase_auth_smoke(
    *,
    env: dict[str, str] | None = None,
    fetcher: JwksFetcher | None = None,
    verifier_factory: VerifierFactory = SupabaseJwtVerifier.from_settings,
) -> CheckReport:
    report = CheckReport("supabase_auth_smoke")
    jwks_url = env_value("SUPABASE_AUTH_JWKS_URL", env)
    issuer = env_value("SUPABASE_AUTH_ISSUER", env)
    audience = env_value("SUPABASE_AUTH_AUDIENCE", env)
    token = env_value("TEST_SUPABASE_JWT", env)
    if not jwks_url:
        report.add("jwks_url", "FAIL", "SUPABASE_AUTH_JWKS_URL is required")
        return report
    if not issuer:
        report.add("issuer", "FAIL", "SUPABASE_AUTH_ISSUER is required")
    else:
        report.add("issuer", "PASS", "Issuer configured", issuer=sanitized_url(issuer))
    if not audience:
        report.add("audience", "WARN", "SUPABASE_AUTH_AUDIENCE is not configured")
    _fetch_jwks(report, jwks_url, fetcher=fetcher)
    if token:
        try:
            settings = Settings(
                app_env="staging",
                auth_mode="supabase_jwt",
                db_connection_mode="local",
                storage_backend="local",
                supabase_auth_jwks_url=jwks_url,
                supabase_auth_issuer=issuer,
                supabase_auth_audience=audience,
            )
            payload = verifier_factory(settings).verify(token)
            subject = str(payload.get("sub") or "")
            report.add("test_jwt", "PASS", "TEST_SUPABASE_JWT verified", subject_prefix=subject[:8])
        except AppError as exc:
            report.add(
                "test_jwt",
                "FAIL",
                "TEST_SUPABASE_JWT verification failed",
                error_code=exc.error_code,
            )
    else:
        report.add("test_jwt", "WARN", "TEST_SUPABASE_JWT not provided; skipped token verification")
    clear_jwks_cache()
    return report


def _fetch_jwks(report: CheckReport, jwks_url: str, *, fetcher: JwksFetcher | None) -> None:
    try:
        if fetcher is None:
            with urlopen(jwks_url, timeout=5.0) as response:  # nosec B310
                payload = cast(JsonPayload, json.loads(response.read().decode("utf-8")))
        else:
            payload = fetcher(jwks_url)
    except Exception as exc:
        report.add(
            "jwks_fetch",
            "FAIL",
            "JWKS fetch failed",
            url=sanitized_url(jwks_url),
            error=type(exc).__name__,
        )
        return
    keys = payload.get("keys")
    if not isinstance(keys, list) or not keys:
        report.add(
            "jwks_keys", "FAIL", "JWKS response has no keys array", url=sanitized_url(jwks_url)
        )
    else:
        typed_keys = cast(list[object], keys)
        report.add(
            "jwks_keys",
            "PASS",
            "JWKS keys available",
            url=sanitized_url(jwks_url),
            key_count=len(typed_keys),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Supabase Auth/JWKS smoke check.")
    add_common_json_arg(parser)
    args = parser.parse_args()
    print_and_exit(run_supabase_auth_smoke(), json_output=args.json)


if __name__ == "__main__":
    main_guard(main)
