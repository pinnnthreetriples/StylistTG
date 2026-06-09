---
name: backend api change
description: Workflow for FastAPI route, module service, schema, and backend contract changes.
triggers:
  - FastAPI
  - endpoint
  - router
  - schema
  - backend module
edges:
  - .mex/context/backend.md
  - .mex/context/security.md
  - .mex/context/conventions.md
  - .mex/patterns/architecture-change.md
  - docs/architecture/AGENT_ARCHITECTURE_GUIDE.md
last_updated: 2026-06-09
---

# Backend API Change

## Context

Load `.mex/context/backend.md` and `.mex/context/security.md`. Find the router, module owner, service/facade, schema/contracts, and tests before editing.

If the change affects module ownership, source-of-truth, wrappers, queues, workflow identifiers, or generated architecture artifacts, also use `.mex/patterns/architecture-change.md`.

## Steps

1. Keep route handlers thin; they validate, authorize, and delegate.
2. Put module behavior in module-owned services, facades, contracts, repositories, policies, or workflow helpers under `backend/app/modules/`.
3. Use `backend/app/services/` only for shared infrastructure or documented compatibility wrappers.
4. Preserve auth and workspace scoping.
5. Add or update contracts/schemas without exposing secrets, runtime paths, TDLib paths, proxy passwords, env values, or unsafe message bodies.
6. Update frontend API client artifacts if the OpenAPI contract changes.
7. Add targeted pytest coverage.

## Verify

```powershell
cd backend; python -m pytest -q
cd backend; python -m ruff check .
npm run check:api
```

Use narrower pytest commands first when practical.

For structural module changes:

```powershell
cd backend
uv run python scripts/structure_audit.py
uv run pytest tests/architecture -q
```
