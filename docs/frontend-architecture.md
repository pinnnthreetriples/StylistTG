# Frontend Architecture Notes

StylistTG uses React + Vite, TanStack Router for canonical navigation, and TanStack Query for server state.

## Route Contract

TanStack Router is the canonical routing layer. Current canonical routes:

- `/` - account list
- `/settings` - settings/readiness
- `/auth/batch` - batch account auth
- `/accounts/$accountId` - account workspace default/profile
- `/accounts/$accountId/profile` - profile editor focus
- `/accounts/$accountId/jobs` - job progress/history focus
- `/accounts/$accountId/stories` - stories focus
- `/accounts/$accountId/music` - profile music focus
- `/accounts/$accountId/debug` - technical details/debug focus

Use `src/lib/routes.ts` for route string creation in new code and tests. Do not add ad-hoc route strings inside components.

`src/router.tsx` defines the route tree, route loaders, and legacy query URL redirects.

Legacy compatibility redirects:

- `/?view=settings` -> `/settings`
- `/?view=auth-batch` -> `/auth/batch`
- `/?account_id=<id>` -> `/accounts/<id>`

Old query URLs are compatibility inputs only. Do not reintroduce query-param phase routing as a primary navigation model.

## Server State

TanStack Query is the canonical server-state layer.

Core files:

- `src/router.tsx` - TanStack Router route tree and route-level prefetch.
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
- Prefer targeted cache updates or scoped invalidation after mutations.
- Full skeletons are for cold loads only. If cached data exists, render it and show background refresh state lightly.

## Route Expansion Rules

- Add new product areas as TanStack Router routes first, then wire UI.
- Keep old query URLs as redirects only when compatibility is needed.
- Use route loaders with existing query options and `queryClient.ensureQueryData`/`prefetchQuery`.
- Keep TanStack Query keys stable when adding or moving routes.
