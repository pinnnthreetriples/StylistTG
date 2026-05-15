---
name: backend
description: FastAPI backend structure, data model, and service boundaries.
triggers:
  - backend
  - FastAPI
  - service
  - model
edges:
  - .mex/context/architecture.md
  - .mex/context/security.md
  - .mex/context/workers.md
last_updated: 2026-05-15
---

# Backend

## Layout

- `backend/app/main.py` registers API routers, middleware, diagnostics, and lifespan loops.
- `backend/app/api/` contains FastAPI routers.
- `backend/app/services/` contains shared services and compatibility wrappers
  while module-owned behavior migrates under `backend/app/modules/`.
- `backend/app/adapters/` contains TDLib/profile/warmup adapter boundaries and mock fallbacks.
- `backend/app/workers/` contains RQ worker entrypoints and queue handlers.
- `backend/tests/` contains pytest tests and shared fakes in `conftest.py`.

## Important routers

- `/api/accounts`, `/api/dashboard`, `/api/jobs`, `/api/workers`
- `/api/accounts/auth-sessions` for auth sessions
- `/api/warmup` for account preparation
- `/health`, `/ready`, diagnostics endpoints

## Data model rules

- Workspace scoping is mandatory for user-owned resources.
- Current profile truth lives in `account_profile_state`.
- Warmup truth lives in `warmup_session` and related warmup tables.
- Operation/audit metadata must be sanitized before persistence.

## Commands

```powershell
cd backend; python -m alembic upgrade head
cd backend; python -m uvicorn app.main:app --reload --port 8002
cd backend; python -m pytest -q
cd backend; python -m ruff check .
```

## Change guidance

- Prefer service-layer fixes over route-only patches.
- For module-owned features, prefer module contracts/facades/enqueue helpers over
  legacy wrappers.
- Update OpenAPI artifacts when backend schema changes affect frontend contracts.
- Add or update pytest coverage for auth, workspace, queue, and warmup behavior changes.
