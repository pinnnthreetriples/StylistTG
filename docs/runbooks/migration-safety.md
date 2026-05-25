# Migration Safety Runbook

Production migrations must favor short metadata-only changes, explicit backfills, and reversible deploy steps. Treat large tenant tables such as `account`, `account_quarantines`, `account_status_observations`, `cross_module_load_buckets`, and `neuro_comment_events` as online-schema-change candidates.

## Required Rules

1. Do not add a `NOT NULL` column to an existing table without a `server_default`.
2. Do not change an existing column to `nullable=False` without a `server_default`, an explicit backfill plan, or an empty-table whitelist.
3. Do not `DROP COLUMN` in the same release that removes code usage. Use two deploys and annotate the migration with `# safe: column unused in code since release X.Y`.
4. Avoid blocking `ALTER TABLE` operations on large tables. If a large-table operation is expected, annotate it with `# expected: requires online schema change` and schedule it for a low-traffic window.
5. Keep downgrade paths reversible unless the migration is deliberately irreversible and documented in the PR.

## Low-Risk Examples

- Add a nullable column.
- Add a non-null column with a safe `server_default`, then remove the default in a later migration if needed.
- Add an index concurrently or through an online schema path appropriate for the production database.

## High-Risk Examples

- `op.alter_column(..., nullable=False)` on a populated table without a default or backfill.
- `op.drop_column(...)` without a prior release proving application code no longer reads it.
- Index or constraint creation on `account` without an online-schema-change note.

## Local Check

Run the migration linter before opening a PR:

```powershell
git fetch origin main
cd backend
python -m tools.migration_lint --base origin/main
```

The linter fails unsafe `NOT NULL` and `DROP COLUMN` patterns and warns on large-table operations that need explicit online-schema-change handling.

## Migration Replay Procedure

Before promoting a release containing schema changes, prove the migrations are reversible against a representative dataset on a disposable Postgres instance. Closes audit findings F-E002, F-E003, F-E006.

```powershell
# 1. Bring up disposable Postgres (port 15432 so it does not collide with dev).
docker compose -f docker-compose.replay.yml up -d
# Wait for the healthcheck to flip green.

# 2. Apply migrations to head and seed a synthetic dataset.
$env:DATABASE_URL = "postgresql://replay:replay@localhost:15432/replay"
cd backend
python -m alembic upgrade head
python -m scripts.seed_safety_replay_dataset --accounts 10000 --workspaces 50

# 3. Drive an upgrade -> downgrade -> upgrade roundtrip with timing capture.
python -m scripts.migration_replay --direction roundtrip --output ../replay-roundtrip.json

# 4. Render the timings into the audit log Markdown.
python -m scripts.migration_replay --format-as-markdown `
    --input ../replay-roundtrip.json `
    --output ../docs/audits/2026-05-safety-pipeline-audit/11-migration-replay-log.md

# 5. Cleanup.
cd ..
docker compose -f docker-compose.replay.yml down -v
Remove-Item Env:DATABASE_URL
```

Safety constraints:

- **Disposable only.** Never run the replay scripts with a production or staging `DATABASE_URL` — the seed step is a destructive bootstrap that assumes empty tables.
- **Deterministic seed.** `seed_safety_replay_dataset.py` uses `random.seed(42)` so timing snapshots are comparable across runs.
- **No mounted volume.** `docker-compose.replay.yml` declares the data dir as `tmpfs`; tearing the container down with `-v` guarantees no state survives.
- If a single migration takes longer than 5 seconds in the roundtrip, open a follow-up to rewrite it as `CREATE INDEX CONCURRENTLY` / batched backfill before promoting the release.
