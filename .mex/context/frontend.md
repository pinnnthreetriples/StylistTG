---
name: frontend
description: Dashboard monorepo, routes, API client, and UI boundary rules.
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
  - docs/api/frontend.md
last_updated: 2026-06-09
---

# Frontend

This file is a navigation map, not a full frontend description. Verify route/module/API facts in source before editing docs.

## Source-of-truth lookup

| Question | Check first | Then check |
| --- | --- | --- |
| Which dashboard routes exist? | `apps/dashboard/src/router.tsx` | `apps/dashboard/src/lib/routes.ts` |
| Which frontend module owns UI code? | `apps/dashboard/src/modules/` | `docs/frontend/frontend-ownership-audit.md` if regenerated/current |
| Which generated API contracts exist? | `packages/api-client/src/` | `packages/api-client/openapi.json`, `docs/api/frontend.md` |
| Which shared UI primitives exist? | `packages/ui/` | app-local `apps/dashboard/src/components/ui/` compatibility pieces |
| Which product/design rules apply? | `.agents/context/PRODUCT.md`, `.agents/context/DESIGN.md` | `.mex/patterns/frontend-module-change.md` |
| Which backend port does dashboard dev use? | `.env.example`, Vite config, `scripts/start-dev.ps1` | README local-dev notes |

## Layout rules

- Dashboard app: `apps/dashboard`.
- Shared API client: `packages/api-client`.
- Shared product UI: `packages/ui`.
- Shared TypeScript config: `packages/config`.
- Product module boundaries are under `apps/dashboard/src/modules/`.
- Current frontend modules include `account-editing`, `auth`, `neuro-commenting`, and `warmup`, each exporting through `index.ts`.

## Runtime rules

- `npm run dev` runs Turborepo dev.
- `npm run dashboard:dev` runs the dashboard Vite server only.
- Vite proxies `/api`, `/health`, `/ready`, and `/diagnostics` to backend localhost port `8002`; verify in source before changing.

## API/client rules

- Prefer package `@stylisttg/api-client` for typed transport.
- `apps/dashboard/src/lib/api.ts` remains a compatibility wrapper for existing imports.
- Older `apps/dashboard/src/lib/auth.ts`, `apps/dashboard/src/lib/authBatches.ts`, `apps/dashboard/src/lib/preview.ts`, and auth/profile hooks may remain compatibility re-exports during frontend modularization.
- Use polling-first query flows; do not add WebSocket/SSE assumptions.
- Account workspace routes must loader-first fetch `authState` and `dashboardBundle`.

## UI boundary rules

- Product modules should use package `@stylisttg/ui` when an equivalent primitive exists.
- App-local or shadcn-compatible UI pieces may remain during migration; do not assume they are fully removed.
- Do not create a parallel design system from `apps/dashboard/src/components/ui/`.
- Use `.agents/context/PRODUCT.md` and `.agents/context/DESIGN.md` for UI/vibecoding work.
- Keep UI minimal, clean, compact, and not visually bulky.
