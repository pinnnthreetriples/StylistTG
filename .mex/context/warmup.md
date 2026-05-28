---
name: warmup
description: Account Preparation / Warmup module memory and safety gates.
triggers:
  - warmup
  - account preparation
  - WARMUP
  - micro-session
edges:
  - .mex/context/workers.md
  - .mex/context/security.md
  - docs/runbooks/account-preparation.md
last_updated: 2026-05-28
---

# Account Preparation / Warmup

## Implemented surfaces

- Backend module router: `backend/app/modules/warmup/router.py` under
  `/api/warmup`; `backend/app/api/warmup.py` remains a compatibility wrapper.
- Frontend route: `/modules/warmup`.
- Frontend module: `apps/dashboard/src/modules/warmup`.
- Helper route: `apps/dashboard/src/routes/WarmupRoute.tsx`.
- Canonical warmup backend boundary: `app.modules.warmup` with contracts,
  repository, policies, errors, read models, queries, commands, service facade,
  jobs, worker, dispatcher, events, isolation, readiness, and p2p.

## Persistence

Warmup state uses `WarmupStrategy`, `WarmupSession`, `WarmupEvent`, `WarmupTaskRun`, `WarmupTrustedPeer`, and `WarmupIsolationClaim`. `warmup_session` is the source of truth for account-preparation state; account API responses expose derived warmup summaries.

## Execution

- Dry-run sessions use `warmup_jobs`.
- Shadow/live micro-session dispatch uses `warmup_dispatch_jobs`.
- Scheduler enqueue is gated by `WARMUP_SCHEDULER_ENABLED`, `WARMUP_WORKERS_ENABLED`, and `WARMUP_HARD_DISABLE`.
- Workflow types remain `warmup_due_sessions` and `warmup_dispatch_tick`; no-arg
  RQ handlers remain under `app.modules.warmup.jobs`.

## Live safety gates

- Live warmup requires `WARMUP_LIVE_ENABLED=true`.
- Mode-specific gates are `WARMUP_PASSIVE_ENABLED`, `WARMUP_NETWORK_ENABLED`, and `WARMUP_ADVANCED_ENABLED`.
- Never enable live warmup against real Telegram accounts without explicit operator approval.
- Warmup does not promise anti-ban or restriction bypass behavior.

## Tests

```powershell
cd backend; python -m pytest tests/test_warmup.py tests/test_warmup_worker.py -q
cd backend; python -m pytest tests/test_warmup_dispatch.py tests/test_warmup_passive.py tests/test_warmup_network_advanced.py tests/test_warmup_isolation.py -q
```
