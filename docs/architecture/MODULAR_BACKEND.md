# Modular Backend

## Goal

The backend uses business modules under `backend/app/modules/` so new feature
work can be organized by domain instead of spreading code across `api/`,
`services/`, `workers/`, and `job_queue/`.

Architecture Epic Phase 6B closes the initial module split by making remaining
legacy feature boundaries explicit, accepted, and guarded. Existing public API
paths, job models, job states, workflow identifiers, and worker behavior remain
the compatibility contract.

## Current Phase: Stabilized Module Boundaries

The current backend has canonical modules for account editing, account
lifecycle, account profile completeness, account safety, auth, neuro commenting,
and warmup. Warmup is split into canonical contracts, repository, policies,
errors, query/read-model, command, router, worker, and dispatcher modules. This
remains compatibility-first: public routes, workflow identifiers, models, queues,
deterministic job ids, no-arg handlers, and worker behavior remain the
compatibility contract.

- `FeatureModule` stores lazy `router_path` strings, not `APIRouter` objects.
- `main.py` registers module routers through `app.modules.registry.iter_routers()`.
- Existing API routers remain the public entrypoints.
- Account update legacy service and worker modules remain as compatibility wrappers.
- Warmup legacy service and worker modules remain as compatibility wrappers.
- `app.services.auth_context` remains a compatibility wrapper around
  `app.modules.auth`.
- Module names may differ from workflow types.

## Module Rules

- A module may expose workflow metadata through `FeatureModule`.
- A module may expose a facade that delegates to existing services.
- A module must not force public API path changes.
- A module must not introduce a new workflow type for an existing persisted workflow.
- Cross-cutting runtime behavior should remain in existing shared services until a
  separate migration has tests for the full behavior.
- Module boundary rules are enforced by tests in `backend/tests/architecture/`.
  See `docs/architecture/boundary-enforcement.md`.

## Account Editing Module

`app.modules.account_editing` is the module wrapper for manual Telegram account
profile updates.

Important compatibility rules:

- Module name: `account_editing`.
- Workflow type: `account_update`.
- Public API path: `/api/account-update`.
- Queue: `profile_jobs`.
- Handler path: `app.modules.account_editing.jobs:run_account_update_job`.

Canonical account update ownership now lives in:

- `app.modules.account_editing.service` for preview, job creation, enqueue, and
  inline fallback use cases.
- `app.modules.account_editing.contracts` for account update Pydantic API DTOs.
- `app.modules.account_editing.enqueue` for account update workflow enqueue and
  delayed retry ownership.
- `app.modules.account_editing.policies` for business preconditions, safety
  checks, asset validation, and profile step selection.
- `app.modules.account_editing.repository` for account/job/asset DB helper
  delegation.
- `app.modules.account_editing.planner` for account update planning and intent
  hashing.
- `app.modules.account_editing.executor` for account update execution and
  materialization.
- `app.modules.account_editing.jobs` for the RQ-compatible handler wrapper.

Legacy paths remain available as compatibility wrappers:

- `app.services.account_update_jobs`
- `app.services.account_update_plan`
- `app.workers.account_update_jobs`

These wrappers should not regain ownership of new account update behavior.
See `docs/architecture/legacy-wrapper-audit.md` for the current wrapper map and
removal conditions.

## Phase 3B: Account Editing Internal Split

`account_editing` is now split into stable internal layers:

- `service.py` remains the use-case facade used by the API and compatibility
  wrappers.
- `contracts.py` owns account update API DTOs while `app.schemas` re-exports
  them for import compatibility.
- `enqueue.py` owns account update workflow enqueue semantics while
  `app.job_queue.rq` keeps compatibility wrapper functions.
- `policies.py` owns account update preconditions, safety blockers, cooldown
  checks, asset validation, and exact legacy error messages.
- `repository.py` owns DB/helper delegation for accounts, assets, duplicate jobs,
  and job finalization.
- `planner.py` still owns plan construction and execution intent hashing.
- `executor.py` still owns job execution and result materialization.

Warmup has since been split into equivalent module-owned internals; see the
Warmup Module section below.

## Phase 3D: Account Editing Typed Errors

`account_editing` now owns typed domain errors in
`app.modules.account_editing.errors`.

- Module internals raise `AccountEditingError` subclasses for stable account
  update failures such as missing accounts, runtime unusable accounts, manual
  intervention blockers, profile cooldowns, asset validation failures, and story
  capability blockers.
- Public API behavior remains compatible: `/api/account-update` maps typed
  errors to the same status codes, `error_code`, `error_class`, messages, and
  field errors that legacy string-based `ValueError` handling exposed.
- Legacy `ValueError` messages remain stable for old import paths. The
  compatibility wrappers in `app.services.account_update_jobs` convert typed
  module errors back into `ValueError` for callers that still depend on that
  surface.
- String-based API mapping remains as a fallback for shared or legacy validation
  paths that have not been converted to typed account editing errors.
- This was not a global backend error refactor.

## Warmup Module

`app.modules.warmup` is the canonical module boundary for warmup. The warmup
split is behavior-preserving and does not change public API paths, workflow
types, queue names, deterministic job ids, no-arg handlers, model behavior, or
TDLib/live execution gates.

Current workflows:

- `warmup_due_sessions`
- `warmup_dispatch_tick`

Both warmup workflows use no-arg handlers and keep their existing queue names and
deterministic job ids.

Current ownership rules:

- Public warmup API paths remain unchanged.
- `app.modules.warmup.contracts` owns warmup Pydantic API DTOs.
- `app.modules.warmup.repository` owns warmup ORM query helpers.
- `app.modules.warmup.policies` owns warmup business/state-transition rules.
- `app.modules.warmup.errors` owns typed module-scoped warmup errors.
- `app.modules.warmup.read_models` owns DTO assembly from warmup runtime state.
- `app.modules.warmup.queries` owns read-only use cases.
- `app.modules.warmup.commands` owns mutating use cases.
- `app.modules.warmup.enqueue` owns warmup workflow enqueue helpers and
  deterministic warmup job ids.
- `app.modules.warmup.router` is the FastAPI presentation boundary.
- `app.modules.warmup.service` remains the stable facade and re-exports query
  and command functions for router and legacy wrapper compatibility.
- `app.modules.warmup.jobs` is the canonical no-arg RQ handler entrypoint.
- Legacy worker entrypoints delegate to module jobs.
- Existing `app.services.warmup*` files are compatibility wrappers.
- Warmup isolation, readiness, p2p, event, worker, and dispatcher
  implementations live under `app.modules.warmup`.

See `docs/architecture/WARMUP_MODULE.md` for the warmup-specific boundary.

## Phase 7: Lazy Router Registry

Module routers are registered through lazy metadata:

- `app.modules.account_editing.module` declares
  `router_path="app.modules.account_editing.router:router"`.
- `app.modules.warmup.module` declares
  `router_path="app.modules.warmup.router:router"`.
- `app.modules.registry` resolves router paths only when `main.py` calls
  `iter_routers()`.

Legacy API modules remain import-compatible by aliasing to the module router
modules. Non-module routers are still manually registered in `main.py`.

## Account Update Reference Audit

| Reference | Location | Category | Keep or migrate later | Reason |
| --- | --- | --- | --- | --- |
| `/api/account-update` router | `backend/app/api/account_update.py` | Public API compatibility | Keep | Public route remains stable while it calls the module facade. |
| `account_update_router` include | `backend/app/main.py` | Public API compatibility | Keep | Router registry is intentionally not enabled yet. |
| `enqueue_account_update_job` | `backend/app/job_queue/rq.py` | Public API compatibility | Keep as compatibility wrapper | Existing imports can still call it; it delegates to `app.modules.account_editing.enqueue`. |
| `reenqueue_job_with_delay(..., workflow_type="account_update")` | `backend/app/job_queue/rq.py` | Candidate for future cleanup | Keep for now | Retry API is shared worker infrastructure; account_update branch now uses workflow metadata. |
| `account_editing.module` workflow metadata | `backend/app/modules/account_editing/module.py` | Workflow metadata | Keep | Declares stable `account_update` workflow metadata. |
| `account_editing.service` facade | `backend/app/modules/account_editing/service.py` | Workflow metadata | Keep | First runtime path through the module facade. |
| `account_editing.jobs` wrapper | `backend/app/modules/account_editing/jobs.py` | Workflow metadata | Keep | Lazy workflow handler path targets this wrapper. |
| `execute_account_update_job` and `run_account_update_job` | `backend/app/modules/account_editing/executor.py` | Worker implementation | Keep | Module-owned executor preserves the previous worker behavior. |
| `account_update` planning/job creation | `backend/app/modules/account_editing/planner.py`, `backend/app/modules/account_editing/service.py` | Worker implementation | Keep | Module-owned code preserves planning, dedup, and creation behavior. |
| Legacy account update services/workers | `backend/app/services/account_update_plan.py`, `backend/app/services/account_update_jobs.py`, `backend/app/workers/account_update_jobs.py` | Public API compatibility | Keep as wrappers | Existing import paths remain stable while canonical ownership moves to the module. |
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

## Future Module Work

Possible future work should stay narrow and is not Architecture Epic closure
debt:

- Continue splitting account editing internals only when behavior-matching tests
  exist first.
- Continue warmup cleanup only as behavior-preserving slices guarded by
  architecture and runtime tests.
- Retire legacy compatibility functions only after call-site audits show no users.
- Extend architecture contracts when new modules need new public interfaces.
