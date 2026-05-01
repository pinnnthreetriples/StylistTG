from __future__ import annotations

import argparse

from app.scripts.cloud_config_check import validate_cloud_config
from app.scripts.common import CheckReport, add_common_json_arg, env_value, load_env_file, main_guard, print_and_exit
from app.scripts.neon_smoke import run_neon_smoke
from app.scripts.object_storage_smoke import run_object_storage_smoke
from app.scripts.redis_smoke import run_redis_smoke
from app.scripts.supabase_auth_smoke import run_supabase_auth_smoke


def run_cloud_smoke(
    *,
    include_redis: bool = False,
    include_storage: bool = False,
    allow_write_cloud: bool = False,
    allow_migrations: bool = False,
    allow_production: bool = False,
) -> CheckReport:
    report = CheckReport("cloud_smoke")
    for child in (
        validate_cloud_config(),
        run_neon_smoke(readonly=True, check_migrations=allow_migrations, upgrade_head=False, allow_production=allow_production),
        run_supabase_auth_smoke(),
    ):
        _extend(report, child)
    if include_redis and env_value("REDIS_URL"):
        _extend(report, run_redis_smoke(allow_production=allow_production))
    elif include_redis:
        report.add("redis_smoke", "WARN", "REDIS_URL missing; Redis smoke skipped")
    if include_storage:
        _extend(
            report,
            run_object_storage_smoke(
                allow_write_cloud=allow_write_cloud,
                allow_production=allow_production,
            ),
        )
    return report


def _extend(report: CheckReport, child: CheckReport) -> None:
    for result in child.results:
        report.results.append(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Combined safe cloud smoke orchestrator.")
    parser.add_argument("--safe-default", action="store_true", help="Run the default read-only/dry-run smoke set.")
    parser.add_argument("--include-redis", action="store_true")
    parser.add_argument("--include-storage", action="store_true")
    parser.add_argument("--allow-write-cloud", action="store_true")
    parser.add_argument("--allow-migrations", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    add_common_json_arg(parser)
    args = parser.parse_args()
    load_env_file(args.env_file)
    print_and_exit(
        run_cloud_smoke(
            include_redis=args.include_redis,
            include_storage=args.include_storage,
            allow_write_cloud=args.allow_write_cloud,
            allow_migrations=args.allow_migrations,
            allow_production=args.allow_production,
        ),
        json_output=args.json,
    )


if __name__ == "__main__":
    main_guard(main)

