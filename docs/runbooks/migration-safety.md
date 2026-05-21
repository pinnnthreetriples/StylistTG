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
