import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  Outlet,
  redirect,
} from '@tanstack/react-router'

import { queryClient } from '@/lib/queryClient'
import {
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  globalOperationLogsQueryOptions,
  settingsBundleQueryOptions,
} from '@/lib/queries'
import { resolveLegacyQueryRoute } from '@/lib/routes'
import { RouteError } from '@/routes/error'
import { RoutePending } from '@/routes/pending'

const AccountsRouteComponent = lazyRouteComponent(() => import('@/routes/AccountsRoute'), 'AccountsRoute')
const SettingsRouteComponent = lazyRouteComponent(() => import('@/routes/AccountsRoute'), 'SettingsRoute')
const AuthBatchRouteComponent = lazyRouteComponent(() => import('@/routes/AuthBatchRoute'), 'AuthBatchRoute')
const OperationsRouteComponent = lazyRouteComponent(() => import('@/routes/OperationsRoute'), 'OperationsRoute')
const AccountWorkspaceRouteComponent = lazyRouteComponent(
  () => import('@/routes/AccountWorkspaceRoute'),
  'AccountWorkspaceRoute',
)

const rootRoute = createRootRoute({
  beforeLoad: ({ location }) => {
    if (location.pathname !== '/') return
    const canonicalRoute = resolveLegacyQueryRoute(location.searchStr)
    if (canonicalRoute) {
      throw redirect({ href: canonicalRoute, replace: true })
    }
  },
  component: () => <Outlet />,
})

const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  loader: () => queryClient.ensureQueryData(accountsQueryOptions()),
  component: AccountsRouteComponent,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'settings',
  loader: () => queryClient.ensureQueryData(settingsBundleQueryOptions()),
  component: SettingsRouteComponent,
})

const authBatchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'auth/batch',
  component: AuthBatchRouteComponent,
})

const operationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'operations',
  loader: () => queryClient.ensureQueryData(globalOperationLogsQueryOptions(100)),
  component: OperationsRouteComponent,
})

function loadAccountWorkspace(accountId: string) {
  return Promise.all([
    queryClient.ensureQueryData(authStateQueryOptions(accountId)),
    queryClient.ensureQueryData(dashboardBundleQueryOptions(accountId)),
  ])
}

const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="profile" />,
})

const accountProfileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/profile',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="profile" />,
})

const accountJobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/jobs',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="jobs" />,
})

const accountStoriesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/stories',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="stories" />,
})

const accountMusicRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/music',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="music" />,
})

const accountDebugRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/debug',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="debug" />,
})

const routeTree = rootRoute.addChildren([
  accountsRoute,
  settingsRoute,
  authBatchRoute,
  operationsRoute,
  accountRoute,
  accountProfileRoute,
  accountJobsRoute,
  accountStoriesRoute,
  accountMusicRoute,
  accountDebugRoute,
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPendingComponent: RoutePending,
  defaultErrorComponent: RouteError,
  defaultPendingMs: 600,
  defaultPendingMinMs: 250,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
