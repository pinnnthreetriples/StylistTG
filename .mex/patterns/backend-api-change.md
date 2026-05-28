---
name: backend api change
description: Workflow for FastAPI route/service/schema changes.
triggers:
  - FastAPI
  - endpoint
  - router
  - schema
edges:
  - .mex/context/backend.md
  - .mex/context/security.md
  - .mex/context/conventions.md
last_updated: 2026-05-28
---

# Backend API Change

## Context

Load `.mex/context/backend.md` and `.mex/context/security.md`. Find the router, service, schema, and tests before editing.

## Steps

1. Keep route handlers thin; put business logic in services.
2. Preserve auth and workspace scoping.
3. Add or update schemas without exposing secrets/runtime paths.
4. Update frontend API client artifacts if the OpenAPI contract changes.
5. Add targeted pytest coverage.

## Verify

```powershell
cd backend; python -m pytest -q
cd backend; python -m ruff check .
npm run check:api
```

Use narrower pytest commands first when practical.
