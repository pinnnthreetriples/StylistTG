from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import UTC, datetime

import psycopg
from sqlalchemy import create_engine, text


AGGREGATE_TABLES = ["account", "job", "asset", "auth_batch", "account_operation_log"]
DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000002"


def main() -> None:
    admin_url = os.environ["DATABASE_ADMIN_URL"]
    base_url = os.environ["DATABASE_BASE_URL"]
    stamp = f"{int(time.time())}_{os.getpid()}"
    empty_db = f"stylisttg_migration_smoke_empty_{stamp}"
    seeded_db = f"stylisttg_migration_smoke_seeded_{stamp}"
    for db_name in (empty_db, seeded_db):
        _create_database(admin_url, db_name)
    try:
        print("empty_upgrade_head", _run_alembic(base_url, empty_db, "upgrade", "head"))
        print(
            "empty_downgrade_0018", _run_alembic(base_url, empty_db, "downgrade", "20260430_0018")
        )
        print("seeded_upgrade_0018", _run_alembic(base_url, seeded_db, "upgrade", "20260430_0018"))
        before = _seed_0018(base_url, seeded_db)
        print("seeded_counts_before", before)
        print("seeded_upgrade_head", _run_alembic(base_url, seeded_db, "upgrade", "head"))
        after, workspace_ids, asset_storage = _inspect_seeded(base_url, seeded_db)
        print("seeded_counts_after", after)
        print("workspace_ids", workspace_ids)
        print("asset_storage", asset_storage)
        _assert_seeded_upgrade(before, after, workspace_ids, asset_storage)
        print("seeded_backfill_ok")
    finally:
        for db_name in (empty_db, seeded_db):
            _drop_database(admin_url, db_name)
        print("temporary_dbs_removed")


def _create_database(admin_url: str, db_name: str) -> None:
    _assert_safe_db_name(db_name)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        connection.execute(f'CREATE DATABASE "{db_name}"')


def _drop_database(admin_url: str, db_name: str) -> None:
    _assert_safe_db_name(db_name)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (db_name,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


def _run_alembic(base_url: str, db_name: str, *args: str) -> str:
    database_url = f"{base_url}/{db_name}"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["DATABASE_DIRECT_URL"] = database_url
    result = subprocess.run(
        ["python", "-m", "alembic", *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return "ok"


def _seed_0018(base_url: str, db_name: str) -> dict[str, int]:
    engine = create_engine(f"{base_url}/{db_name}")
    ids = {key: str(uuid.uuid4()) for key in AGGREGATE_TABLES}
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into account (id, external_ref, auth_source, account_state, created_at, updated_at) "
                "values (:id, '+15550123000', 'manual', 'execution_usable', :now, :now)"
            ),
            {"id": ids["account"], "now": now},
        )
        connection.execute(
            text(
                "insert into job (id, account_id, job_state, execution_intent_hash, job_payload_version, "
                "payload_json, plan_json_snapshot) values (:id, :account_id, 'completed', "
                "'seeded-intent', 1, '{}'::json, '{}'::json)"
            ),
            {"id": ids["job"], "account_id": ids["account"]},
        )
        connection.execute(
            text(
                "insert into asset (id, kind, source_path, normalized_path, content_hash, mime, status, created_at) "
                "values (:id, 'profile_photo', 'source.jpg', 'normalized.jpg', 'hash', 'image/jpeg', 'ready', :now)"
            ),
            {"id": ids["asset"], "now": now},
        )
        connection.execute(
            text(
                "insert into auth_batch (id, status, total_count, success_count, failed_count, cancelled_count, "
                "skipped_count, max_running_commands, max_waiting_input, max_total_active, idempotency_key, "
                "version, created_at) values (:id, 'completed', 1, 1, 0, 0, 0, 1, 1, 1, 'seeded-key', 1, :now)"
            ),
            {"id": ids["auth_batch"], "now": now},
        )
        connection.execute(
            text(
                "insert into account_operation_log (id, account_id, operation_type, status, severity, source, "
                "message, metadata_json, created_at) values (:id, :account_id, 'seeded', 'success', 'info', "
                "'smoke', 'seeded log', '{}'::json, :now)"
            ),
            {"id": ids["account_operation_log"], "account_id": ids["account"], "now": now},
        )
    with engine.connect() as connection:
        return _counts(connection, AGGREGATE_TABLES)


def _inspect_seeded(
    base_url: str,
    db_name: str,
) -> tuple[dict[str, int], dict[str, list[str]], dict[str, str | None]]:
    engine = create_engine(f"{base_url}/{db_name}")
    with engine.connect() as connection:
        counts = _counts(
            connection,
            AGGREGATE_TABLES + ["workspace", "app_user", "workspace_member", "workspace_plan"],
        )
        workspace_ids = {
            table_name: [
                row[0]
                for row in connection.execute(
                    text(f"select workspace_id::text from {table_name}")
                ).all()
            ]
            for table_name in AGGREGATE_TABLES
        }
        asset_storage_row = connection.execute(
            text(
                "select storage_backend, source_key, normalized_key, source_path, normalized_path "
                "from asset limit 1"
            )
        ).one()
        asset_storage = {
            "storage_backend": asset_storage_row[0],
            "source_key": asset_storage_row[1],
            "normalized_key": asset_storage_row[2],
            "source_path": asset_storage_row[3],
            "normalized_path": asset_storage_row[4],
        }
    return counts, workspace_ids, asset_storage


def _counts(connection, table_names: list[str]) -> dict[str, int]:
    return {
        table_name: connection.execute(text(f"select count(*) from {table_name}")).scalar_one()
        for table_name in table_names
    }


def _assert_seeded_upgrade(
    before: dict[str, int],
    after: dict[str, int],
    workspace_ids: dict[str, list[str]],
    asset_storage: dict[str, str | None],
) -> None:
    for table_name in AGGREGATE_TABLES:
        if before[table_name] != 1 or after[table_name] != 1:
            raise AssertionError(
                f"{table_name} row count changed: before={before[table_name]} after={after[table_name]}"
            )
        if workspace_ids[table_name] != [DEFAULT_WORKSPACE_ID]:
            raise AssertionError(
                f"{table_name} workspace backfill failed: {workspace_ids[table_name]}"
            )
    for table_name in ("workspace", "app_user", "workspace_member", "workspace_plan"):
        if after[table_name] != 1:
            raise AssertionError(f"{table_name} bootstrap count failed: {after[table_name]}")
    if asset_storage["storage_backend"] != "local":
        raise AssertionError(f"asset storage backend backfill failed: {asset_storage}")
    if (
        asset_storage["source_key"] != "source.jpg"
        or asset_storage["normalized_key"] != "normalized.jpg"
    ):
        raise AssertionError(f"asset storage key backfill failed: {asset_storage}")
    if (
        asset_storage["source_path"] != "source.jpg"
        or asset_storage["normalized_path"] != "normalized.jpg"
    ):
        raise AssertionError(f"asset legacy path preservation failed: {asset_storage}")


def _assert_safe_db_name(db_name: str) -> None:
    if not db_name.startswith("stylisttg_migration_smoke_"):
        raise ValueError("refusing to create/drop non-smoke database")


if __name__ == "__main__":
    main()
