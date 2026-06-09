---
name: frontend module change
description: Workflow for dashboard route, module, product UI, and frontend boundary changes.
triggers:
  - dashboard
  - route
  - UI
  - React
  - frontend module
edges:
  - .mex/context/frontend.md
  - .mex/context/conventions.md
  - .agents/context/PRODUCT.md
  - .agents/context/DESIGN.md
last_updated: 2026-06-09
---

# Frontend Module Change

## Context

Load `.mex/context/frontend.md`. For UI or product-facing work, also load `.agents/context/PRODUCT.md` and `.agents/context/DESIGN.md`. Check `apps/dashboard/src/router.tsx`, `apps/dashboard/src/lib/routes.ts`, API helpers, public module indexes, and module-specific tests before editing.

## Steps

1. Use existing route helpers instead of hardcoding paths.
2. Prefer package `@stylisttg/api-client` for typed transport.
3. Prefer package `@stylisttg/ui` for product UI primitives when an equivalent exists.
4. Keep polling-first data flow; do not add WebSocket/SSE assumptions.
5. Preserve loader-first account workspace behavior.
6. Keep feature code behind module public indexes; avoid feature-to-feature deep imports.
7. Keep UI minimal, clean, compact, and not visually bulky.
8. Use Russian user-facing copy unless a technical identifier is clearer in English.
9. Add or update vitest coverage for logic and components when relevant.

## Verify

```powershell
npm test
npm run lint
npm run typecheck
```

Run focused workspace tests first when possible.
