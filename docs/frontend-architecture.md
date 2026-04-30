# Frontend Architecture Notes

StylistTG uses React + Vite, TanStack Router for canonical navigation, and TanStack Query for server state.

## Route Contract

TanStack Router is the canonical routing layer. Current canonical routes:

- `/` - account list
- `/settings` - settings/readiness
- `/auth/batch` - batch account auth
- `/operations` - global operation log journal
- `/accounts/$accountId` - account workspace default/profile
- `/accounts/$accountId/profile` - profile editor focus
- `/accounts/$accountId/jobs` - job progress/history focus
- `/accounts/$accountId/stories` - stories focus
- `/accounts/$accountId/music` - profile music focus
- `/accounts/$accountId/debug` - technical details/debug focus

Use `src/lib/routes.ts` for route string creation in new code and tests. Do not add ad-hoc route strings inside components.

`src/router.tsx` defines the route tree, route loaders, lazy route components, and legacy query URL redirects.

Route screen wrappers live in `src/routes/`:

- `AccountsRoute.tsx` - accounts/settings area chunk.
- `AuthBatchRoute.tsx` - batch auth chunk.
- `OperationsRoute.tsx` - global operation logs chunk.
- `AccountWorkspaceRoute.tsx` - account editor/workspace chunk.
- `pending.tsx` - small cold-load pending fallback.
- `error.tsx` - product route loader/component error fallback with hidden technical details.

Use TanStack Router's `lazyRouteComponent` for route-level code splitting. Do not add random `React.lazy`
inside product components for routing concerns. Split at product route boundaries first, then consider
nested route chunks only when a module becomes a true independent page.

Legacy compatibility redirects:

- `/?view=settings` -> `/settings`
- `/?view=auth-batch` -> `/auth/batch`
- `/?account_id=<id>` -> `/accounts/<id>`

Old query URLs are compatibility inputs only. Do not reintroduce query-param phase routing as a primary navigation model.

## Server State

TanStack Query is the canonical server-state layer.

Core files:

- `src/router.tsx` - TanStack Router route tree, lazy route components, route loaders, and route-level prefetch.
- `src/lib/queryClient.ts` - shared default options.
- `src/lib/queries.ts` - query keys, query options, cache helpers.
- `src/hooks/queries/useAccountsQueries.ts` - accounts list and prefetching.
- `src/hooks/queries/useSettingsQueries.ts` - settings bundle and settings mutations.
- `src/hooks/queries/useDashboardMutations.ts` - dashboard mutation invalidation.
- `src/hooks/useDashboardJobPolling.ts` - active job polling.

Rules:

- Import query keys/options from `src/lib/queries.ts`; do not create ad-hoc keys in components.
- Keep account-specific dashboard data under `queryKeys.dashboard.account(accountId)` so cleanup removes all account-scoped cache.
- Use `dashboardBundleQueryOptions(accountId)` for the current editor bootstrap because it avoids sequential loading waterfalls.
- Use granular options (`dashboardProfileQueryOptions`, `storyDraftsQueryOptions`, `storyCapabilitiesQueryOptions`, job queries) when a future page needs one sub-resource independently.
- Use proxy/log options from `src/lib/queries.ts` for account proxy, proxy summary, account operation logs, and global operation logs.
- Prefer targeted cache updates or scoped invalidation after mutations.
- Full skeletons are for cold loads only. If cached data exists, render it and show background refresh state lightly.

## Route Expansion Rules

- Add new product areas as TanStack Router routes first, then wire UI.
- Keep old query URLs as redirects only when compatibility is needed.
- Use route loaders with existing query options and `queryClient.ensureQueryData`/`prefetchQuery`.
- Keep TanStack Query keys stable when adding or moving routes.
- Preserve loader-first rendering for account workspace routes: `authState` and `dashboardBundle` should be ready before the editor renders.
- Use small route pending fallbacks for true cold loads only; do not show full skeletons during warm cached navigation.
- Route loader/component errors should use TanStack Router error components, not ad-hoc top-level banners.
