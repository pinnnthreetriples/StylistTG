from __future__ import annotations

import argparse
import json
import sys

from app.config import settings
from app.services.tdlib_runtime import detect_tdlib_runtime


def _build_payload(*, runtime_check: bool, library_check: bool, readonly_auth_check: bool, auth_session_id: str | None) -> tuple[dict, bool]:
    status = detect_tdlib_runtime(settings)
    payload = status.to_safe_dict()
    checks: dict[str, str] = {}

    checks["runtime"] = "PASS" if runtime_check or not (library_check or readonly_auth_check) else "SKIP"
    if library_check:
        checks["library"] = "PASS" if (not status.library_configured or status.library_loadable) else "FAIL"
    else:
        checks["library"] = "SKIP"

    if readonly_auth_check:
        if not (settings.tdlib_live_enabled and settings.tdlib_readonly_smoke_enabled):
            checks["readonly_auth"] = "DISABLED"
            payload["readonly_auth_check"] = "disabled"
        elif not auth_session_id:
            checks["readonly_auth"] = "SKIP"
            payload["readonly_auth_check"] = "auth_session_id_required"
        else:
            checks["readonly_auth"] = "SKIP"
            payload["readonly_auth_check"] = "not_implemented_without_existing_auth_session"
    else:
        checks["readonly_auth"] = "DISABLED"

    failed = any(result == "FAIL" for result in checks.values())
    payload["checks"] = checks
    payload["status"] = "FAIL" if failed else "PASS"
    return payload, not failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe TDLib runtime smoke check")
    parser.add_argument("--runtime-check", action="store_true", help="check TDLib runtime configuration")
    parser.add_argument("--library-check", action="store_true", help="check tdjson loadability")
    parser.add_argument("--readonly-auth-check", action="store_true", help="reserved explicit live readonly auth check")
    parser.add_argument("--auth-session-id", help="existing auth session id for future read-only auth smoke")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args(argv)

    payload, ok = _build_payload(
        runtime_check=args.runtime_check,
        library_check=args.library_check,
        readonly_auth_check=args.readonly_auth_check,
        auth_session_id=args.auth_session_id,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
