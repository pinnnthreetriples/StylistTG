---
name: frontend module change
description: Workflow for dashboard route/module/UI changes.
triggers:
  - dashboard
  - route
  - UI
  - React
edges:
  - .mex/context/frontend.md
  - .mex/context/conventions.md
last_updated: 2026-05-28
---

# Frontend Module Change

## Context

Load `.mex/context/frontend.md`. Check `apps/dashboard/src/router.tsx`, `apps/dashboard/src/lib/routes.ts`, API helpers, and module-specific tests.

## Steps

1. Use existing route helpers instead of hardcoding paths.
2. Prefer packages @stylisttg/api-client and @stylisttg/ui.
3. Keep polling-first data flow.
4. Preserve loader-first account workspace behavior.
5. Add or update vitest coverage for logic and components when relevant.

## Verify

```powershell
npm test
npm run lint
npm run typecheck
```

Run focused workspace tests first when possible.
