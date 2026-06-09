---
name: frontend
description: Dashboard monorepo, routes, API client, and UI conventions.
triggers:
  - frontend
  - dashboard
  - route
  - React
edges:
  - .mex/context/architecture.md
  - .mex/context/conventions.md
  - .mex/patterns/frontend-module-change.md
  - .agents/context/PRODUCT.md
  - .agents/context/DESIGN.md
last_updated: 2026-06-08
---

# Frontend

## Layout

- Dashboard app: `apps/dashboard`.
- Shared API client: `packages/api-client`.
- Shared product UI: `packages/ui`.
- Shared TypeScript config: `packages/config`.
- Product module boundaries are under `apps/dashboard/src/modules/`.
- Current frontend modules include `account-editing`, `auth`, `neuro-commenting`, and `warmup`, each exporting through `index.ts`.

## Runtime

- `npm run dev` runs Turborepo dev.
- `npm run dashboard:dev` runs the dashboard Vite server only.
- Vite proxies `/api`, `/health`, `/ready`, and `/diagnostics` to backend localhost port `8002`.

## Routes

Canonical frontend routes include `/home`, `/accounts`, `/accounts/add`, account workspace sections, `/health`, `/jobs`, `/modules/neuro-commenting`, `/modules/warmup`, `/proxy`, `/settings`, and `/billing`.

## API/client rules

- Prefer package `@stylisttg/api-client` for typed transport.
- `apps/dashboard/src/lib/api.ts` remains a compatibility wrapper for existing imports.
- Older `apps/dashboard/src/lib/auth.ts`, `apps/dashboard/src/lib/authBatches.ts`, `apps/dashboard/src/lib/preview.ts`, and auth/profile hooks may remain compatibility re-exports during frontend modularization.
- Use polling-first query flows; do not add WebSocket/SSE assumptions.
- Account workspace routes must loader-first fetch `authState` and `dashboardBundle`.

## UI rules

- Product modules should use package `@stylisttg/ui` when an equivalent primitive exists.
- Use `.agents/context/PRODUCT.md` and `.agents/context/DESIGN.md` for UI/vibecoding work.
- Do not create a parallel design system from `apps/dashboard/src/components/ui/`.
- Keep UI minimal, clean, compact, and not visually bulky.
