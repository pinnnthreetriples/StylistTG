# Migration Replay Log

> Closes audit findings **F-E002** (no end-to-end replay evidence),
> **F-E003** (no timing snapshot), **F-E006** (no reversibility proof).
>
> Replay procedure documented in
> [`docs/runbooks/migration-safety.md`](../../runbooks/migration-safety.md#migration-replay-procedure).
> Infrastructure: `docker-compose.replay.yml` (disposable Postgres 17 on
> port 15432, `tmpfs` data dir, no persistent volume).
> Scripts: `backend/scripts/seed_safety_replay_dataset.py`,
> `backend/scripts/migration_replay.py`.

## Bulk replay (full upgrade → downgrade roundtrip)

Executed 2026-05-25 against disposable Postgres 17 on Windows
(WSL bash + native Docker). Schema dropped and re-created between runs.

| Phase | Direction | Elapsed | Final state |
| --- | --- | ---: | --- |
| Phase 1 | `alembic upgrade base → head` | **130.9 s** | head revision `20260523_0053`, 63 tables created |
| Phase 2 | `alembic downgrade head → base` | **130.8 s** | schema back to empty, `alembic_version` cleared |

**Total roundtrip:** 261.7 s for 106 migration steps (53 upgrade + 53
downgrade). No lock timeouts, no FK violations, no data-loss errors.

Both directions completed cleanly — every migration in
`backend/migrations/versions/20260423_0001_*.py` through
`backend/migrations/versions/20260523_0053_*.py` is reversible.

## Per-migration timing — follow-up

The bulk-replay number above proves reversibility (the goal of F-E002 /
F-E003 / F-E006), but does not break the cost down per revision. A
per-revision timing pass driven by `scripts/migration_replay.py
--direction roundtrip` was attempted and aborted: each
`command.upgrade(cfg, target)` invocation re-parses the migration script
directory and reopens the SQLAlchemy engine, so the per-step overhead
dwarfs the actual DDL cost for the small migrations in this release.
Investigating a lower-level alembic API to keep the connection warm
across revisions is tracked as a follow-up in the Task 46 PR review
thread. Until then the bulk numbers above are the canonical replay
artefact.

## Synthetic dataset

`scripts/seed_safety_replay_dataset.py` is committed but **best-effort**:
it seeds 1 owner user + N workspaces + N accounts + safety-pipeline
state with `random.seed(42)` for determinism. Schema changes can leave
the seed script behind — it does not run during CI and should be
treated as a starting point, not a contract. The bulk replay numbers
above were captured against an empty schema; production replay should
run against a sampled prod dataset (see runbook).

## Lossy downgrade notes

The full roundtrip succeeded on an empty schema — no rows existed to be
lost during downgrade. Migrations identified as lossy under populated
schemas (operator must review before downgrading prod):

| Migration | Lossy on downgrade | Mitigation |
| --- | --- | --- |
| `20260520_0038_account_behavior_profile_nullable_typing` | `typing_speed_baseline_cpm NULL → NOT NULL` on re-upgrade requires backfill | Document: downgrade requires manual backfill before re-upgrade |
| `20260520_0046_account_origin` | `accounts.origin` drop loses `bought` / `created` distinction | Acceptable: post-Task-18 forward only |
| `20260520_0049_attempt_idempotency_keys` | Drop `idempotency_key` unique + column loses reconcile capability | Document: downgrade only safe with reconcile worker turned off |

## Cleanup

After replay:

```powershell
docker compose -f docker-compose.replay.yml down -v
```

The `-v` flag is required — without it the tmpfs data dir is unmounted
but compose keeps the (empty) network. The replay container must not
survive into the next test run.
