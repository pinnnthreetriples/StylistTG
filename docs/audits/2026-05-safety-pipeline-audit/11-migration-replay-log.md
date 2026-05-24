# Migration Replay Log

## Status

Full replay was **not run** in this local audit session.

Reason: issue #148 requires a staging-size or synthetic disposable database with at least 10k accounts. No approved disposable Postgres dataset was available. Running `alembic downgrade base` against the configured database would be destructive and violates audit safety constraints.

## Static Baseline

| Check | Result |
| --- | --- |
| Migration files | 49 files in `backend/migrations/versions` |
| Alembic heads | `20260523_0053 (head)` |
| Replay evidence | Missing |
| Local blocker | No safe disposable DB; full pytest collection also blocked by missing `prometheus_client` |

## Static Findings Affecting Replay Confidence

| Finding | Summary |
| --- | --- |
| F-E002 | Migration replay/downgrade reversibility is not proven. |
| F-E003 | Large-table migrations lack online-schema rollout notes. |
| F-E006 | Downgrade of nullable typing speed is data-lossy. |
| F-E001 | Account-owned safety tables can block account deletion because cascade/cleanup policy is inconsistent. |

## Required Replay Procedure

```powershell
cd backend
# Use disposable Postgres only.
python -m alembic downgrade base
python -m alembic upgrade head
# Seed >=10k synthetic accounts plus safety tables.
python scripts/seed_safety_replay_dataset.py --accounts 10000 --workspace replay
python -m alembic downgrade base
python -m alembic upgrade head
python -m tools.migration_lint --base origin/main
```

## Expected Output For Future Completion

| Migration | Upgrade ms | Downgrade ms | Row count before | Row count after | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `20260423_0001`..`20260523_0053` | TBD | TBD | TBD | TBD | Not run in this audit. |

Until this log is replaced with real timings from a disposable DB, production readiness remains conditional.
