# Safety Pipeline Backfill Runbook

## When To Run

Run this backfill when enabling `safety_pipeline_v2_enabled` for a workspace that already has accounts created before the safety pipeline rollout. The script creates missing GGR scores, behavior baselines, imported origin markers where absent, and a 30 day safety grace period for each account in one workspace.

Do not run against production without explicit operator approval.

## Pre-Flight

Confirm the target workspace ID and verify the migration `20260522_0052_account_safety_grace_period.py` has been applied. Run a dry run first:

```powershell
cd backend
python -m scripts.backfill_safety_pipeline --workspace-id <workspace-uuid> --dry-run --batch-size 1000
```

Check the JSON summary for expected account counts. Do not read `.env*`, logs, `backend/tdlib/`, or runtime artifacts while preparing the run.

## Staging Procedure

1. Apply migrations in staging.
2. Run the dry run command for the staging workspace.
3. Run the execute command with a small batch first:

```powershell
cd backend
python -m scripts.backfill_safety_pipeline --workspace-id <workspace-uuid> --batch-size 100
```

4. Re-run with `--dry-run`; created counts should be zero.
5. Exercise safety-gated commenting checks for a known account without live TDLib calls.

## Prod Procedure

Production execution requires explicit operator approval. After approval, run:

```powershell
cd backend
python -m scripts.backfill_safety_pipeline --workspace-id <workspace-uuid> --batch-size 1000
```

Use smaller batches for large workspaces if DB load needs tighter control. The script commits once per batch and only touches rows scoped to the supplied workspace.

## Rollback

The migration is reversible:

```powershell
cd backend
python -m alembic downgrade 20260522_0051
```

For data rollback, prefer a targeted DB restore or explicit operator-approved cleanup based on `neuro_comment_events.data_json.batch_run_id`. Do not delete existing GGR scores or behavior profiles unless an operator approves a specific cleanup plan.

## Verification Queries

Use read-only queries scoped by workspace:

```sql
select count(*) from account where workspace_id = '<workspace-uuid>';
select count(*) from account_ggr_scores where workspace_id = '<workspace-uuid>';
select count(*) from account_behavior_profile where workspace_id = '<workspace-uuid>';
select count(*) from account where workspace_id = '<workspace-uuid>' and safety_grace_period_until is not null;
select count(*) from neuro_comment_events where workspace_id = '<workspace-uuid>' and event_type = 'safety_backfill_executed';
```

Expected result after a successful first run: each account has a GGR row, behavior profile, and `safety_grace_period_until`.

## Known Limitations

The script does not trigger async GGR recalculation. New GGR rows are initialized with `score=5.0`, `bucket='medium'`, and `next_calculation_at` due so existing scheduler work can recalculate later.

The 30 day grace period only relaxes conservative workspace mode to balanced mode inside the account safety gate cross-module load check. Balanced and aggressive policies are unchanged.
