# Modular Backend

## Goal

The backend is moving toward business modules under `backend/app/modules/` so feature
work can be organized by domain instead of spreading new code across `api/`,
`services/`, `workers/`, and `job_queue/`.

The current goal is a safe foundation, not a large rewrite. Existing public API
paths, job models, job states, workflow identifiers, and worker behavior remain
the compatibility contract.

## Current Phase: Wrap-First, Not Rewrite

The current phase is wrap-first. Modules provide metadata and thin facades over
existing services/workers. They do not own all business logic yet.

- `FeatureModule` intentionally has no `router` field in this phase.
- Router registry is not enabled in `main.py`.
- Existing API routers remain the public entrypoints.
- Existing service and worker modules remain the source of implemented behavior.
- Module names may differ from workflow types.

## Module Rules

- A module may expose workflow metadata through `FeatureModule`.
- A module may expose a facade that delegates to existing services.
- A module must not force public API path changes.
- A module must not introduce a new workflow type for an existing persisted workflow.
- Cross-cutting runtime behavior should remain in existing shared services until a
  separate migration has tests for the full behavior.

## Account Editing Module

`app.modules.account_editing` is the module wrapper for manual Telegram account
profile updates.

Important compatibility rules:

- Module name: `account_editing`.
- Workflow type: `account_update`.
- Public API path: `/api/account-update`.
- Queue: `profile_jobs`.
- Handler path: `app.modules.account_editing.jobs:run_account_update_job`.

The module facade currently delegates preview and job creation to
`app.services.account_update_jobs`. Enqueue and delayed retry now use workflow
metadata for `account_update`, while the existing worker implementation remains in
`app.workers.account_update_jobs`.

## Warmup Module

`app.modules.warmup` is metadata/wrapper-only in the current phase.

Current workflows:

- `warmup_due_sessions`
- `warmup_dispatch_tick`

Both warmup workflows use no-arg handlers. Warmup API, services, dispatch logic,
and worker implementations have not been migrated into module-owned internals.

## Account Update Reference Audit

| Reference | Location | Category | Keep or migrate later | Reason |
| --- | --- | --- | --- | --- |
| `/api/account-update` router | `backend/app/api/account_update.py` | Public API compatibility | Keep | Public route remains stable while it calls the module facade. |
| `account_update_router` include | `backend/app/main.py` | Public API compatibility | Keep | Router registry is intentionally not enabled yet. |
| `enqueue_account_update_job` | `backend/app/job_queue/rq.py` | Public API compatibility | Keep as compatibility wrapper | Existing imports can still call it; it delegates to workflow registry. |
| `reenqueue_job_with_delay(..., workflow_type="account_update")` | `backend/app/job_queue/rq.py` | Candidate for future cleanup | Keep for now | Retry API is shared worker infrastructure; account_update branch now uses workflow metadata. |
| `account_editing.module` workflow metadata | `backend/app/modules/account_editing/module.py` | Workflow metadata | Keep | Declares stable `account_update` workflow metadata. |
| `account_editing.service` facade | `backend/app/modules/account_editing/service.py` | Workflow metadata | Keep | First runtime path through the module facade. |
| `account_editing.jobs` wrapper | `backend/app/modules/account_editing/jobs.py` | Workflow metadata | Keep | Lazy workflow handler path targets this wrapper. |
| `execute_account_update_job` and `run_account_update_job` | `backend/app/workers/account_update_jobs.py` | Worker implementation | Keep | Actual worker behavior still lives here. |
| `account_update` planning/job creation | `backend/app/services/account_update_plan.py`, `backend/app/services/account_update_jobs.py` | Worker implementation | Keep | Business behavior and dedup are not being rewritten in this phase. |
| `account_update` handling in profile worker | `backend/app/workers/profile_jobs.py` | Worker implementation | Keep | Shared profile execution engine still classifies account update outcomes. |
| Account update tests | `backend/tests/**` | Test-only | Keep | Tests cover legacy behavior, module metadata, enqueue compatibility, and worker behavior. |

## What Must Not Be Changed Casually

- `/api/account-update`
- `workflow_type="account_update"`
- `Job` model fields and indexes
- `JobState`
- `execution_intent_hash` dedup behavior
- Warmup runtime behavior
- Router registration in `main.py`
- TDLib/live execution gates

## Future Migration Phases

Possible future phases should stay narrow:

- Move more account update service calls behind the module facade.
- Add module-owned policies only after matching existing behavior with tests.
- Introduce router registry only after duplicate-route risks are handled.
- Move warmup internals only as separate dry-run/shadow/live-safe slices.
- Retire legacy compatibility functions only after call-site audits show no users.
