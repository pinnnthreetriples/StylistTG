---
name: stack
description: Technology stack and package/tooling choices.
triggers:
  - stack
  - dependency
  - package
  - tooling
edges:
  - .mex/context/setup.md
  - .mex/context/backend.md
  - .mex/context/frontend.md
last_updated: 2026-05-25
---

# Stack

## Frontend

- React + TypeScript + Vite.
- Turborepo with npm workspaces.
- Tailwind CSS v4.
- TanStack Router, Query, Table/Form/Virtual foundations.
- Package @stylisttg/api-client for generated OpenAPI transport.
- Package @stylisttg/ui for shared product UI.

## Backend

- Python 3.12+.
- FastAPI.
- SQLAlchemy and Alembic.
- PostgreSQL.
- Redis + RQ.
- TDLib through `tdjson.dll` where live runtime is explicitly enabled.

## Tooling

- Frontend: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
- Browser QA: `npm run qa:browser`, `npm run qa:screenshots`.
- Backend: `python -m pytest -q`, `python -m ruff check .`.
- API drift: `npm run generate:api`, `npm run check:api`.
- Memory drift: `npm run memory:check` after mex CLI installation.

## Package manager

The root package manager is `npm@11.12.1`. Ask before installing or updating dependencies.
