# Monorepo Architecture

StylistTG now uses npm workspaces with Turborepo for frontend-side packages and tasks.

## Layout

```text
backend/                 FastAPI, RQ workers, Alembic, Dockerfile
apps/dashboard/          Vite React dashboard app
packages/api-client/     OpenAPI schema artifact, generated TS types, typed fetch helpers
packages/ui/             Shared frontend UI primitives
packages/config/         Shared TypeScript config
```

`backend/` intentionally stays at the repository root. The staging API and worker deploy path is stable on `backend/Dockerfile`, so moving it to `apps/api` is deferred to a separate deployment-aware PR.

## Commands

```powershell
npm run dashboard:dev
npm run generate:api
npm run check:api
npm run lint
npm test
npm run build
npm run qa:browser
```

Turborepo runs package tasks in dependency order. `dev` is persistent and uncached; `generate:api` regenerates the FastAPI OpenAPI artifact and TypeScript schema; `check:api` verifies committed generated artifacts are current without rewriting them.

## Packages

- `@stylisttg/dashboard`: current product dashboard under `apps/dashboard`.
- `@stylisttg/api-client`: `openapi-fetch` client plus generated `openapi-typescript` schema.
- `@stylisttg/ui`: shared primitives such as `Button`, `Badge`, `StatusPill`, `DataTable`, and page layout components.
- `@stylisttg/config`: shared TS config for workspace packages.

No package reads cloud secrets at build time.

Browser QA lives in `apps/dashboard/e2e` and uses Playwright with mocked API data, so it does not require staging cloud resources.
