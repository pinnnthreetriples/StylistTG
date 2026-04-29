# Frontend Architecture Notes

StylistTG currently uses React + Vite with a lightweight URL contract and TanStack Query for server state.

## Route Contract

Current routes are intentionally small:

- `/` - account list
- `/?view=settings` - settings/readiness
- `/?view=auth-batch` - batch account auth
- `/?account_id=<id>` - profile editor for an account

Use `src/lib/routes.ts` for route string creation in new code and tests. Keep route helpers narrow: do not add future-only routes until the UI actually supports them.

`src/lib/appView.ts` parses the current top-level `view` value. `src/lib/appNavigation.ts` owns pure navigation-state transitions. `src/hooks/useAppNavigation.ts` binds those helpers to browser history and React transitions.

## Server State

TanStack Query is the canonical server-state layer.

Core files:

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

## Future Routing

Do not mix feature work with a full router migration.

The next routing step, when needed, should be a dedicated slice:

1. Keep `src/lib/routes.ts` as the route manifest.
2. Move path/search parsing into route-level adapters.
3. Preserve existing URL compatibility or provide redirects.
4. Keep TanStack Query keys stable during routing migration.

TanStack Router can be introduced later if nested pages, typed search params, route loaders, or route-level preloading become a real constraint. The current architecture is prepared for that without forcing the migration now.
