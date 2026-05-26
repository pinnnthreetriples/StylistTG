# Frontend Ownership Audit

Generated snapshot: `2026-05-17T00:00:00Z`

This audit records the dashboard ownership surfaces after the Phase 23 cleanup pass. The goal is to move feature-specific code behind module public APIs while keeping old import paths compatible.

| Current path | Feature owner | Target module | Migration status | Compatibility path | Notes |
| --- | --- | --- | --- | --- | --- |
| `apps/dashboard/src/lib/api.ts` | shared / mixed | `modules/shared`, feature modules | partial | unchanged named exports | Account-update job and story draft helpers now delegate to `modules/account-editing/api`; unrelated API helpers remain global to avoid a broad rewrite. |
| `apps/dashboard/src/lib/dashboard.ts` | account-editing / app-shell | `modules/account-editing` | partial | unchanged named exports | Profile draft state, change mappers, media labels, and execution confirmation helpers moved behind account-editing. App-shell/job banner helpers remain global. |
| `apps/dashboard/src/lib/auth.ts` | auth | `modules/auth` | migrated compatibility wrapper | unchanged path | Re-exports auth runtime/flow helpers from the auth module. |
| `apps/dashboard/src/lib/authBatches.ts` | auth | `modules/auth` | migrated compatibility wrapper | unchanged path | Re-exports auth batch helpers from the auth module. |
| `apps/dashboard/src/lib/appErrors.ts` | shared | `modules/shared` | deferred | unchanged path | Generic error normalization remains global; candidate for a later shared-module pass. |
| `apps/dashboard/src/lib/apiClient.ts` | shared | `modules/shared/api` | partial | unchanged path | `modules/shared/api` now exposes `dashboardApiClient`; old path remains the canonical app shell/client setup. |
| `apps/dashboard/src/lib/queries.ts` | shared / app-shell | `modules/shared` | deferred | unchanged path | Query keys span multiple pages and remain global until feature query ownership can be split safely. |
| `apps/dashboard/src/lib/dashboardCache.ts` | app-shell | app-shell | deferred | unchanged path | Loader/cache bootstrap behavior is app-shell-level. |
| `apps/dashboard/src/lib/dashboardNavigation.ts` | app-shell | app-shell | deferred | unchanged path | Route loader hydration remains app-shell-level. |
| `apps/dashboard/src/lib/dashboardReconciliation.ts` | account-editing | `modules/account-editing` | deferred | unchanged path | Depends on app-shell dashboard refresh flow; safe future candidate. |
| `apps/dashboard/src/lib/uiLabels.ts` | shared / mixed | `modules/shared`, feature labels | deferred | unchanged path | Large label surface; only small auth redaction moved in this PR. |
| `apps/dashboard/src/hooks/useProfileDraft.ts` | account-editing | `modules/account-editing` | migrated compatibility wrapper | unchanged path | Re-exports `useProfileDraft` from module. |
| `apps/dashboard/src/hooks/useAuthBootstrap.ts` | auth | `modules/auth` | migrated compatibility wrapper | unchanged path | Re-exports auth bootstrap hook from module. |
| `apps/dashboard/src/hooks/useAuthFlow.ts` | auth | `modules/auth` | migrated compatibility wrapper | unchanged path | Re-exports auth flow hook from module. |
| `apps/dashboard/src/hooks/useDashboard*.ts` | app-shell / account-editing | app-shell, `modules/account-editing` | deferred | unchanged path | Dashboard orchestration spans auth, profile draft, polling, and loader cache; leave until a dedicated app-shell split. |
| `apps/dashboard/src/hooks/queries/*` | shared / page features | `modules/shared`, future page modules | deferred | unchanged path | Cross-page query adapters remain global. |
| `apps/dashboard/src/components/auth/*` | auth | `modules/auth/components` | deferred | unchanged path | Large JSX/state components were not moved to avoid UI churn. Boundary tests still prevent deep cross-module imports. |
| `apps/dashboard/src/components/dashboard/profile/*` | account-editing | `modules/account-editing/components` | deferred | unchanged path | Profile editor components are safe candidates for a later mechanical path move; skipped to keep PR size controlled. |
| `apps/dashboard/src/components/dashboard/accountWorkspace/*` | account-editing / shared | `modules/account-editing/components`, app-shell | deferred | unchanged path | Workspace panels mix account editing, proxy, risk, and shell concerns. |
| `apps/dashboard/src/components/dashboard/jobs/*` | shared / app-shell | future shared/jobs module | deferred | unchanged path | Job panels are cross-feature and stay global. |
| `apps/dashboard/src/components/ui/*` | shared UI | package `@stylisttg/ui` / app-local UI | deferred | unchanged path | Design-system primitive migration is out of scope. |
| `apps/dashboard/src/features/auth/authUiSecurity.ts` | auth | `modules/auth/labels.ts` | migrated compatibility wrapper | unchanged path | Pure redaction helper moved; old path re-exports it. |
| `apps/dashboard/src/features/auth/AuthSessionWizard.tsx` | auth | `modules/auth/components` | deferred | unchanged path | Not moved because it is a larger screen component with local state. |
| `apps/dashboard/src/features/auth/SupabaseAuthContext.ts` | app-shell / auth | app-shell or `modules/auth` | deferred | unchanged path | Provider/context affects app shell auth bootstrap; leave for a dedicated auth ownership pass. |
| `apps/dashboard/src/features/auth/SupabaseAuthProvider.tsx` | app-shell / auth | app-shell or `modules/auth` | deferred | unchanged path | Not moved to avoid changing provider wiring. |
| `apps/dashboard/src/features/auth/LoginPage.tsx` | auth / route | route feature | deferred | unchanged path | Route-level feature page remains global route surface. |
| `apps/dashboard/src/features/accounts/*` | shared / account management | future accounts module | unknown/deferred | unchanged path | Outside Phase 23 account-editing/auth scope. |
| `apps/dashboard/src/features/account-import/*` | unknown/deferred | future import module | unknown/deferred | unchanged path | Outside current module set. |
| `apps/dashboard/src/features/batch-import/*` | unknown/deferred | future import module | unknown/deferred | unchanged path | Outside current module set. |
| `apps/dashboard/src/features/health/*` | app-shell | app-shell | deferred | unchanged path | Operational page, not feature-module-owned yet. |
| `apps/dashboard/src/features/home/*` | app-shell | app-shell | deferred | unchanged path | Home/dashboard route remains app-shell. |
| `apps/dashboard/src/features/jobs/*` | shared / app-shell | future jobs module | unknown/deferred | unchanged path | Cross-feature job history. |
| `apps/dashboard/src/features/proxy/*` | unknown/deferred | future proxy module | unknown/deferred | unchanged path | Outside current module set. |
| `apps/dashboard/src/features/settings/*` | app-shell | app-shell | deferred | unchanged path | Settings remains route-level shell. |
| `apps/dashboard/src/modules/account-editing/*` | account-editing | `modules/account-editing` | active owner | public index `modules/account-editing` | Owns account update API, profile draft hook, labels, types, and mappers. |
| `apps/dashboard/src/modules/auth/*` | auth | `modules/auth` | active owner | public index `modules/auth` | Owns auth API, batches, hooks, bootstrap, types, and pure labels. |
| `apps/dashboard/src/modules/warmup/*` | warmup | `modules/warmup` | active owner | public index `modules/warmup` | Most mature module; no ownership changes in this PR. |
| `apps/dashboard/src/modules/shared/*` | shared | `modules/shared` | started | public index `modules/shared` | Owns feature-neutral UI/API helpers; must not import feature modules, and feature modules must use the public index except tracked legacy deep imports. |

## Deferred Moves

- Large auth screens, Supabase provider/context, and route pages are intentionally deferred because moving them would create a broad JSX/state path rewrite.
- Dashboard orchestration hooks remain global until an app-shell boundary is designed.
- Global `lib/api.ts` remains a mixed compatibility surface; only account-editing-specific named helpers were moved in this pass.
