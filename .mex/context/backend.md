---
name: backend
description: FastAPI backend structure, data model, and module/service boundaries.
triggers:
  - backend
  - FastAPI
  - service
  - model
edges:
  - .mex/context/architecture.md
  - .mex/context/security.md
  - .mex/context/workers.md
last_updated: 2026-06-08
---

# Backend

## Layout

- `backend/app/main.py` registers API routers, middleware, diagnostics, and lifespan loops.
- `backend/app/api/` contains FastAPI routers that validate, authorize, and delegate.
- `backend/app/modules/` owns module-specific behavior, contracts, facades, repositories, enqueue helpers, and workflow/runtime boundaries.
- `backend/app/services/` contains shared services and compatibility wrappers; do not treat legacy wrappers as new ownership centers.
- `backend/app/adapters/` contains TDLib/profile/warmup adapter boundaries and mock fallbacks.
- `backend/app/workers/` contains RQ worker entrypoints and queue handlers.
- `backend/tests/` contains pytest tests and shared fakes in `conftest.py`.

## Important routers

- `/api/accounts`, `/api/dashboard`, `/api/jobs`, `/api/workers`
- `/api/accounts/auth-sessions` for auth sessions
- `/api/warmup` for account preparation
- `/api/neuro-commenting` for NeuroCommenting foundation: campaigns, targets, campaign accounts, generated comments, approvals, and events
- `/health`, `/ready`, diagnostics endpoints

## Data model rules

- Workspace scoping is mandatory for user-owned resources.
- Current profile truth lives in `account_profile_state`.
- Warmup truth lives in `warmup_session` and related warmup tables.
- NeuroCommenting foundation truth lives in `neuro_comment_*` tables with manual approval and TDLib sending disabled by default.
- Operation/audit metadata must be sanitized before persistence.

## Commands

```powershell
cd backend; python -m alembic upgrade head
cd backend; python -m uvicorn app.main:app --reload --port 8002
cd backend; python -m pytest -q
cd backend; python -m ruff check .
```

## Change guidance

- Prefer module-owned contracts/facades/services over route-only patches or legacy wrapper growth.
- For shared infrastructure, keep service-layer logic focused and workspace-scoped.
- Update OpenAPI artifacts when backend schema changes affect frontend contracts.
- Add or update pytest coverage for auth, workspace, queue, safety, warmup, and neuro-commenting behavior changes.
