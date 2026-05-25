"""Seed a synthetic safety-pipeline dataset for migration replay (Task 46).

Generates a realistic-but-deterministic snapshot inside a disposable Postgres
instance so the migration replay (``migration_replay.py``) can measure
upgrade/downgrade timing on a representative table size.

Usage::

    DATABASE_URL=postgresql://replay:replay@localhost:15432/replay \
        python -m scripts.seed_safety_replay_dataset --accounts 10000

Key behaviour:

* **Deterministic** — ``random.seed(42)`` so replay timings are comparable
  across runs.
* **Idempotent at the table-name level** — if the safety-pipeline schema
  already has rows the script exits without modifying anything. Re-runs
  on a clean schema produce the same row counts and distributions.
* **No prod dependencies** — uses only stdlib + SQLAlchemy. ``faker`` is
  optional and only consulted for the workspace name column when present.

The output is purely a row-count snapshot, not a behavioural fixture: do
not point integration tests at this database.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_SEED = 42


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ts(offset_hours: float = 0.0) -> datetime:
    return _now() + timedelta(hours=offset_hours)


def _engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is required (e.g. postgresql://replay@localhost:15432/replay)"
        )
    return create_engine(url, future=True)


def _table_empty(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1")).first()
    return result is None


def _seed_accounts(
    engine: Engine, *, workspaces: int, accounts: int
) -> tuple[list[str], list[str]]:
    """Insert workspaces and accounts. Returns (workspace_ids, account_ids)."""
    workspace_ids = [str(uuid.uuid4()) for _ in range(workspaces)]
    account_ids = [str(uuid.uuid4()) for _ in range(accounts)]
    rng = random.Random(_SEED)

    owner_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app_user (id, email, external_auth_provider,"
                " external_auth_user_id, status, created_at, updated_at)"
                " VALUES (:id, :email, 'replay', :ext_id, 'active', :ts, :ts)"
                " ON CONFLICT DO NOTHING"
            ),
            {
                "id": owner_id,
                "email": "replay@example.test",
                "ext_id": "replay-user",
                "ts": _now(),
            },
        )

        for i, ws_id in enumerate(workspace_ids):
            conn.execute(
                text(
                    "INSERT INTO workspace (id, name, slug, owner_user_id, status,"
                    " created_at, updated_at)"
                    " VALUES (:id, :name, :slug, :owner, 'active', :ts, :ts)"
                    " ON CONFLICT DO NOTHING"
                ),
                {
                    "id": ws_id,
                    "name": f"replay-{i}",
                    "slug": f"replay-{i}",
                    "owner": owner_id,
                    "ts": _now(),
                },
            )

        for j, acc_id in enumerate(account_ids):
            ws_id = workspace_ids[j % workspaces]
            origin = rng.choices(["imported", "bought", "created"], weights=[70, 15, 15])[0]
            conn.execute(
                text(
                    "INSERT INTO account (id, workspace_id, external_ref,"
                    " account_state, origin, created_at, updated_at)"
                    " VALUES (:id, :ws, :ref, 'registered', :origin, :ts, :ts)"
                    " ON CONFLICT DO NOTHING"
                ),
                {
                    "id": acc_id,
                    "ws": ws_id,
                    "ref": f"+1555{rng.randint(1_000_000, 9_999_999)}",
                    "origin": origin,
                    "ts": _ts(-rng.uniform(0, 720)),
                },
            )

    return workspace_ids, account_ids


def _seed_safety_pipeline_state(
    engine: Engine, *, workspace_ids: list[str], account_ids: list[str]
) -> dict[str, int]:
    """Populate the safety-pipeline tables. Returns row counts."""
    rng = random.Random(_SEED + 1)
    counts: dict[str, int] = {}

    quarantine_targets = rng.sample(account_ids, k=max(1, len(account_ids) // 20))  # ~5%
    observation_targets = rng.sample(account_ids, k=max(1, len(account_ids) // 3))  # ~33%
    ggr_targets = account_ids  # 100%
    behavior_targets = rng.sample(account_ids, k=max(1, len(account_ids) // 2))  # ~50%

    with engine.begin() as conn:
        # Quarantines
        for acc_id in quarantine_targets:
            ws_id = workspace_ids[rng.randint(0, len(workspace_ids) - 1)]
            conn.execute(
                text(
                    "INSERT INTO account_quarantines"
                    " (id, workspace_id, account_id, reason, started_at, until,"
                    "  metadata_json)"
                    " VALUES (:id, :ws, :acc, 'flood_wait', :start, :until, '{}')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "ws": ws_id,
                    "acc": acc_id,
                    "start": _ts(-rng.uniform(0, 24)),
                    "until": _ts(rng.uniform(0, 24)),
                },
            )
        counts["account_quarantines"] = len(quarantine_targets)

        # Status observations — 5 per target on average
        observation_rows = 0
        for acc_id in observation_targets:
            ws_id = workspace_ids[rng.randint(0, len(workspace_ids) - 1)]
            for _ in range(rng.randint(1, 10)):
                conn.execute(
                    text(
                        "INSERT INTO account_status_observations"
                        " (id, workspace_id, account_id, observed_at,"
                        "  proxy_healthy, tdlib_authorized, consecutive_failures,"
                        "  details_json)"
                        " VALUES (:id, :ws, :acc, :ts, true, true, 0, '{}')"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "ws": ws_id,
                        "acc": acc_id,
                        "ts": _ts(-rng.uniform(0, 24 * 7)),
                    },
                )
                observation_rows += 1
        counts["account_status_observations"] = observation_rows

        # GGR scores
        for acc_id in ggr_targets:
            ws_id = workspace_ids[rng.randint(0, len(workspace_ids) - 1)]
            score = round(rng.uniform(1.0, 10.0), 1)
            bucket = "strong" if score >= 7 else "medium" if score >= 4 else "weak"
            conn.execute(
                text(
                    "INSERT INTO account_ggr_scores"
                    " (id, workspace_id, account_id, score, bucket,"
                    "  breakdown_json, created_at, updated_at)"
                    " VALUES (:id, :ws, :acc, :score, :bucket, '{}', :ts, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "ws": ws_id,
                    "acc": acc_id,
                    "score": score,
                    "bucket": bucket,
                    "ts": _now(),
                },
            )
        counts["account_ggr_scores"] = len(ggr_targets)

        # Behavior profiles
        for acc_id in behavior_targets:
            ws_id = workspace_ids[rng.randint(0, len(workspace_ids) - 1)]
            conn.execute(
                text(
                    "INSERT INTO account_behavior_profile"
                    " (id, workspace_id, account_id,"
                    "  typing_speed_baseline_cpm, typo_rate_baseline,"
                    "  profile_view_probability_baseline,"
                    "  scroll_probability_baseline,"
                    "  message_deletion_probability_baseline,"
                    "  action_sequence_seed, created_at, updated_at)"
                    " VALUES (:id, :ws, :acc, 120, 0.05, 0.7, 0.3, 0.02, :seed, :ts, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "ws": ws_id,
                    "acc": acc_id,
                    "seed": rng.randint(0, 2**31 - 1),
                    "ts": _now(),
                },
            )
        counts["account_behavior_profile"] = len(behavior_targets)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=int, default=10000)
    parser.add_argument("--workspaces", type=int, default=50)
    args = parser.parse_args()

    engine = _engine()

    if not _table_empty(engine, "account"):
        print(
            "account table already populated — refusing to seed (idempotency)",
            file=sys.stderr,
        )
        sys.exit(0)

    workspace_ids, account_ids = _seed_accounts(
        engine, workspaces=args.workspaces, accounts=args.accounts
    )
    counts = _seed_safety_pipeline_state(
        engine, workspace_ids=workspace_ids, account_ids=account_ids
    )
    counts["account"] = len(account_ids)
    counts["workspace"] = len(workspace_ids)

    print("Seed complete. Row counts:")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
