# Agent Architecture Guide

This guide is not a full description of StylistTG. It is a code-first navigation guide for agents: find the current source of truth, preserve boundaries, make the smallest safe change, and verify with code-backed checks.

Start here for architecture work:

1. `AGENTS.md`
2. `.mex/ROUTER.md`
3. `.mex/patterns/architecture-change.md`
4. `.mex/context/architecture.md`
5. `.mex/context/decisions.md`
6. this guide
7. `docs/architecture/MODULAR_BACKEND.md`
8. `docs/architecture/STRUCTURE_AUDIT.md`

## Operating Rule

Do not rely on memory or old docs when architecture matters. Locate the owning code first, then update docs/memory only when the change creates stable reusable knowledge.

## Source-of-Truth Lookup

| Question | Check first | Then check |
| --- | --- | --- |
| Which backend module owns this behavior? | `backend/app/modules/registry.py` | `docs/architecture/STRUCTURE_AUDIT.md`, `docs/architecture/architecture-debt-inventory.json` |
| How should a module expose a router? | `backend/app/modules/contracts.py` | existing `backend/app/modules/*/module.py` |
| Where are API routes registered? | `backend/app/main.py` | `backend/app/modules/registry.py` |
| Which queue names exist? | `backend/app/contracts/queues.py` | `.mex/context/workers.md` |
| Which runtime role may use a queue? | `backend/app/runtime/roles.py` | `docs/architecture/production-execution-plane.md` |
| Which state is durable truth? | SQLAlchemy models and migrations | `.mex/context/architecture.md`, module repositories |
| Which frontend module owns UI behavior? | `apps/dashboard/src/modules/` | `docs/frontend/frontend-ownership-audit.md` if regenerated/current |
| What changed structurally? | `uv run python scripts/structure_audit.py` | generated files under `docs/architecture/` |

## Core Architecture Rules

- StylistTG is a compatibility-first modular monolith.
- PostgreSQL-backed models are durable source of truth.
- Redis/RQ is execution infrastructure and cache state, not durable business truth.
- FastAPI routes validate, authorize, and delegate.
- Module-owned feature behavior belongs under `backend/app/modules/<module_name>/`.
- `backend/app/services/` is for shared services and compatibility wrappers, not new feature ownership centers.
- Existing public API paths, queue names, workflow identifiers, deterministic job ids, job states, and worker behavior are compatibility contracts.
- Live TDLib, live warmup, deploy, migrations, and production-like smoke remain explicitly gated.
- Frontend feature modules expose public indexes and avoid feature-to-feature deep imports.

## When A Change Is Architectural

Treat a change as architectural if it affects any of these:

- module ownership;
- backend/app/modules registry or module layout;
- legacy wrappers or compatibility surfaces;
- API route ownership;
- persistent source-of-truth tables/models;
- workflow identifiers or job state;
- queue names or runtime roles;
- worker launch commands;
- frontend module boundaries or public indexes;
- architecture audit artifacts;
- docs under `docs/architecture/`.

For these changes, use `.mex/patterns/architecture-change.md`.

## Backend Module Shape

A new backend module should use only the layers it needs. Do not create empty ceremony files.

Typical shape:

```text
backend/app/modules/<module_name>/
  __init__.py
  module.py              # FeatureModule metadata
  router.py              # FastAPI router, if the module exposes API routes
  contracts.py           # module DTOs and Pydantic contracts
  service.py             # use-case facade
  repository.py          # persistence/query helpers
  queries.py             # read use cases, when useful
  commands.py            # mutating use cases, when useful
  policies.py            # business/safety preconditions
  errors.py              # typed module-scoped errors
  enqueue.py             # enqueue helpers, if jobs are needed
  jobs.py                # RQ-compatible handlers, if jobs are needed
```

Optional specialized layers may exist when justified:

```text
adapters.py
read_models.py
presenters.py
runtime.py
workflow.py
```

## New Module Implementation Checklist

### 1. Define the boundary

Before adding files, identify:

- module name;
- owned domain behavior;
- public API path, if any;
- source-of-truth tables/models;
- queue/workflow needs, if any;
- compatibility surfaces that must remain stable;
- safety/live-runtime implications.

If the module overlaps with an existing module, extend the existing module instead of creating a new one.

### 2. Add module metadata

Create `backend/app/modules/<module_name>/module.py` with lazy metadata. Router paths should be strings, not imported `APIRouter` objects, so app startup remains lazy.

Follow the conventions documented in `docs/architecture/MODULAR_BACKEND.md` and match existing module examples before inventing a new pattern.

### 3. Register the module

Register the module through the existing module registry pattern. Do not add a parallel registry or manual router loading mechanism.

Concretely, update `backend/app/modules/registry.py`:

1. Import the module object as `<module_name>_module`.
2. Add it to the `MODULES` tuple.
3. Keep route-safe ordering. Modules with broad wildcard routes must come after modules with more specific routes they could shadow.
4. Preserve existing ordering comments. For example, `account_core_module` is intentionally last because its `/api/accounts/{account_id}` wildcard can shadow more specific account routes.

`main.py` should continue registering module routers through `app.modules.registry.iter_routers()`.

### 4. Add contracts

Module DTOs and Pydantic contracts should live in `contracts.py` unless they are truly shared platform contracts.

Do not put feature-specific contracts in global shared files just because another module might read them later. Prefer explicit public module facades.

### 5. Add router only if needed

If the module exposes API routes:

- keep router handlers thin;
- validate auth/workspace context;
- delegate to module service/query/command layers;
- do not import ORM models directly in routers;
- do not expose secrets, raw runtime paths, TDLib paths, proxy passwords, env values, or unsafe message bodies.

### 6. Add persistence helpers

Put module-owned query and persistence helpers in `repository.py`, `queries.py`, or `commands.py`.

PostgreSQL is durable truth. Redis/RQ should not become the canonical state for business facts.

### 7. Add enqueue/jobs only if needed

If the module owns asynchronous work:

- define queue usage against `backend/app/contracts/queues.py`;
- define runtime role implications in `backend/app/runtime/roles.py` when applicable;
- keep workflow identifiers stable;
- use deterministic job ids where existing flows require them;
- update worker diagnostics and runbooks;
- update `.mex/context/workers.md` when queue taxonomy changes.

### 8. Keep compatibility wrappers thin

Legacy API/service/worker paths may remain as wrappers. They should delegate to module-owned code and should not regain behavior ownership.

Do not grow these files for new behavior unless the task is explicitly compatibility maintenance.

### 9. Update frontend boundaries when needed

If the backend module has dashboard UI:

- place frontend feature code under `apps/dashboard/src/modules/<feature>/` when it is a product module;
- export through `index.ts`;
- use `@stylisttg/api-client` for typed transport;
- use `@stylisttg/ui` when an equivalent primitive exists;
- app-local or shadcn-compatible UI pieces may remain during migration, but new product primitives should prefer `@stylisttg/ui`;
- consult `.agents/context/PRODUCT.md` and `.agents/context/DESIGN.md` for UI work;
- avoid feature-to-feature deep imports.

### 10. Update documentation and memory

Update only stable, reusable memory:

- `.mex/context/architecture.md` for stable source-of-truth or boundary changes;
- `.mex/context/backend.md`, `frontend.md`, `workers.md`, or `security.md` for domain-specific stable facts;
- `.mex/context/decisions.md` for durable architecture decisions;
- `.mex/patterns/` only when a repeatable workflow changes;
- docs under `docs/architecture/` when architecture facts or generated audits change.

Do not store logs, stack traces, transient command output, or one-off debug notes in memory.

## Architecture Verification

Run the structure audit after structural changes:

```bash
cd backend
uv run python scripts/structure_audit.py
```

Commit generated artifacts when the changes are intentional:

```text
docs/architecture/STRUCTURE_AUDIT.md
docs/architecture/structure-audit.json
docs/architecture/architecture-debt-inventory.json
```

Run architecture tests when module boundaries changed:

```bash
cd backend
uv run pytest tests/architecture -q
```

For docs/memory scaffold changes:

```powershell
npm run memory:check
npm run memory:sync:dry-run
git diff --check
```

## Architecture Decision Rules

Add a decision to `.mex/context/decisions.md` when:

- a new module owner is introduced;
- source-of-truth changes;
- a compatibility wrapper is retained or retired;
- queue taxonomy or runtime role ownership changes;
- frontend module boundaries change;
- live/runtime/deploy safety posture changes.

Mark old decisions as superseded instead of deleting them.

## What Agents Must Not Do

- Do not create a new module because a file is getting large; define a real domain boundary first.
- Do not add new feature behavior under `backend/app/services/` if a module owner exists or should exist.
- Do not create a second module registry.
- Do not bypass `FeatureModule` metadata for module routers.
- Do not change public API paths, workflow identifiers, queue names, or job states without an explicit migration plan.
- Do not use Redis/RQ as durable business truth.
- Do not add live TDLib behavior without explicit operator approval and gates.
- Do not rely on archived handoff text as current architecture authority.

## New Module PR Template

Use this checklist in PR descriptions or issue comments:

```text
Architecture impact:
- New/changed module:
- Owned domain behavior:
- Public API path:
- Source-of-truth tables/models:
- Queue/workflow/runtime role changes:
- Registry update and route ordering:
- Compatibility wrappers touched:
- Frontend module changes:
- Safety/live-runtime implications:
- Architecture artifacts regenerated: yes/no
- Decisions updated: yes/no
- Verification run:
```
