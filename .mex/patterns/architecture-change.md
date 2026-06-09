---
name: architecture-change
description: Workflow for architecture, module ownership, source-of-truth, runtime role, queue, or boundary changes.
triggers:
  - architecture
  - boundary
  - module
  - ownership
  - source of truth
  - runtime role
  - structure audit
edges:
  - .mex/context/architecture.md
  - .mex/context/backend.md
  - .mex/context/frontend.md
  - .mex/context/workers.md
  - .mex/context/security.md
  - .mex/context/decisions.md
  - docs/architecture/AGENT_ARCHITECTURE_GUIDE.md
  - docs/architecture/MODULAR_BACKEND.md
  - docs/architecture/STRUCTURE_AUDIT.md
  - docs/quality/DEVELOPER_WORKFLOW.md
last_updated: 2026-06-09
---

# Architecture Change Pattern

Use this pattern when a task changes module ownership, source-of-truth rules, public module boundaries, API route ownership, runtime roles, queue taxonomy, architecture audit artifacts, or docs under `docs/architecture/`.

## Context

Load:

1. `.mex/context/architecture.md`
2. `.mex/context/decisions.md`
3. Relevant domain context: backend, frontend, workers, warmup, security, or deploy
4. `docs/architecture/AGENT_ARCHITECTURE_GUIDE.md`
5. `docs/architecture/MODULAR_BACKEND.md` for backend modules
6. `docs/architecture/STRUCTURE_AUDIT.md` for current generated boundary state

## Rules

1. Preserve module ownership. New feature behavior belongs under `backend/app/modules/<module_name>/`.
2. Do not grow legacy API/service/worker wrappers unless the task is explicitly compatibility maintenance.
3. Keep FastAPI routes thin: validate, authorize, delegate.
4. Keep PostgreSQL-backed models as durable source of truth.
5. Keep Redis/RQ as execution infrastructure, not durable business truth.
6. Keep queue names and runtime roles in sync across `backend/app/contracts/queues.py`, `backend/app/runtime/roles.py`, worker diagnostics, runbooks, and `.mex/context/workers.md`.
7. Keep frontend features behind module public indexes; avoid feature-to-feature deep imports.
8. Keep live TDLib, warmup, deploy, migration, and production-like behavior explicitly gated.
9. If architecture changes, update generated architecture artifacts through the structure audit pipeline.
10. Record durable architecture decisions in `.mex/context/decisions.md`.

## New Backend Module Checklist

Use `docs/architecture/AGENT_ARCHITECTURE_GUIDE.md` for the full guide. Minimal checklist:

1. Define the module owner and domain boundary.
2. Add `backend/app/modules/<module_name>/` with `__init__.py`, `module.py`, and only the needed layers.
3. Expose routers through lazy `FeatureModule.router_path` metadata when the module has API routes.
4. Put DTOs/contracts in module-owned `contracts.py` unless they are truly shared platform contracts.
5. Put persistence helpers in module-owned repository/query layers.
6. Put enqueue/workflow helpers in module-owned enqueue/jobs layers when jobs are needed.
7. Keep existing public API paths, queue names, workflow identifiers, and job states stable unless an explicit migration plan says otherwise.
8. Add tests before or with behavior changes.
9. Regenerate structure audit artifacts if files, module registry, wrappers, runtime roles, or frontend boundaries changed.

## Verify

For backend architecture changes:

```powershell
cd backend
uv run python scripts/structure_audit.py
uv run pytest tests/architecture -q
```

If generated artifacts changed, commit them intentionally:

```text
docs/architecture/STRUCTURE_AUDIT.md
docs/architecture/structure-audit.json
docs/architecture/architecture-debt-inventory.json
```

For memory/docs scaffold changes:

```powershell
npm run memory:check
npm run memory:sync:dry-run
git diff --check
```

## Gotchas

- A manifest/update to generated architecture docs is not a substitute for canonical migration.
- Compatibility wrappers are not ownership centers.
- Existing public routes and workflow identifiers are compatibility contracts.
- Do not use archived handoff content as current architecture authority.
