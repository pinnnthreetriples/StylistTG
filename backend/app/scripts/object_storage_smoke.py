from __future__ import annotations

import argparse
import uuid

from app.config import Settings
from app.scripts.common import (
    CheckReport,
    add_common_json_arg,
    env_value,
    load_env_file,
    looks_production,
    main_guard,
    print_and_exit,
    require_not_production,
)
from app.storage import build_storage_service


def run_object_storage_smoke(
    *,
    allow_write_cloud: bool = False,
    show_signed_url: bool = False,
    allow_production: bool = False,
    env: dict[str, str] | None = None,
    storage_factory=build_storage_service,
) -> CheckReport:
    report = CheckReport("object_storage_smoke")
    if not require_not_production(report, allow_production=allow_production, env=env):
        return report
    app_env = env_value("APP_ENV", env) or "local"
    bucket = env_value("STORAGE_S3_BUCKET", env)
    if looks_production(bucket) and app_env != "production":
        report.add("bucket_guard", "FAIL", "Production-looking bucket outside production", bucket=bucket)
        return report
    if not allow_write_cloud:
        report.add("dry_run", "PASS", "Dry-run only; no object storage write/read/delete calls were made")
        return report
    try:
        settings = _settings_from_env(env)
        storage = storage_factory(settings)
        prefix = f"smoke/stylisttg/{uuid.uuid4()}"
        key = f"{prefix}/object.txt"
        content = b"stylisttg cloud object storage smoke\n"
        stored = storage.save_bytes(key, content, content_type="text/plain")
        stat = storage.stat(key)
        read_back = storage.read_bytes(key)
        signed_url = storage.get_signed_url(key, expires_seconds=settings.storage_s3_signed_url_expires_seconds)
        deleted = storage.delete(key)
        exists_after_delete = storage.exists(key)
    except Exception as exc:
        report.add("object_storage_write", "FAIL", "Object storage smoke failed", error=type(exc).__name__)
        return report
    if read_back != content or not deleted or exists_after_delete:
        report.add("object_storage_write", "FAIL", "Object storage smoke consistency check failed")
    else:
        details = {"key": stored.key, "size_bytes": stat.size_bytes}
        if show_signed_url:
            details["signed_url"] = signed_url
        else:
            details["signed_url"] = signed_url.split("?", 1)[0]
        report.add("object_storage_write", "PASS", "Object storage write/read/signed-url/delete smoke passed", **details)
    return report


def _settings_from_env(env: dict[str, str] | None) -> Settings:
    if env is None:
        return Settings()
    return Settings(**{key.lower(): value for key, value in env.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe R2/S3 object storage smoke check.")
    parser.add_argument("--dry-run", action="store_true", help="Explicitly run without object storage writes.")
    parser.add_argument("--allow-write-cloud", action="store_true")
    parser.add_argument("--show-signed-url", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    add_common_json_arg(parser)
    args = parser.parse_args()
    load_env_file(args.env_file)
    print_and_exit(
        run_object_storage_smoke(
            allow_write_cloud=args.allow_write_cloud,
            show_signed_url=args.show_signed_url,
            allow_production=args.allow_production,
        ),
        json_output=args.json,
    )


if __name__ == "__main__":
    main_guard(main)

