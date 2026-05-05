import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  Outlet,
  redirect,
} from '@tanstack/react-router'

import { AppShell } from '@/app/AppShell'
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
const SettingsRouteComponent = lazyRouteComponent(() => import('@/routes/SettingsRoute'), 'SettingsRoute')
const AuthBatchRouteComponent = lazyRouteComponent(() => import('@/routes/AuthBatchRoute'), 'AuthBatchRoute')
const OperationsRouteComponent = lazyRouteComponent(() => import('@/routes/OperationsRoute'), 'OperationsRoute')
const HealthCenterRouteComponent = lazyRouteComponent(() => import('@/routes/HealthCenterRoute'), 'HealthCenterRoute')
const JobsRouteComponent = lazyRouteComponent(() => import('@/routes/JobsRoute'), 'JobsRoute')
const BillingRouteComponent = lazyRouteComponent(() => import('@/routes/BillingRoute'), 'BillingRoute')
const ProxyCenterRouteComponent = lazyRouteComponent(() => import('@/routes/ProxyCenterRoute'), 'ProxyCenterRoute')
const AccountWorkspaceRouteComponent = lazyRouteComponent(
  () => import('@/routes/AccountWorkspaceRoute'),
  'AccountWorkspaceRoute',
)

const HomeRouteComponent = lazyRouteComponent(() => import('@/routes/HomeRoute'), 'HomeRoute')

const rootRoute = createRootRoute({
  beforeLoad: ({ location }) => {
    if (location.pathname !== '/') return
    const canonicalRoute = resolveLegacyQueryRoute(location.searchStr)
    if (canonicalRoute) {
      throw redirect({ href: canonicalRoute, replace: true })
    }
    throw redirect({ to: '/home', replace: true })
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
})

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/home',
  component: HomeRouteComponent,
})

const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accounts',
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

const accountAddRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/add',
  component: AuthBatchRouteComponent,
})

// Operations route still exists for deep links / Settings → Advanced
const operationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'operations',
  loader: () => queryClient.ensureQueryData(globalOperationLogsQueryOptions(100)),
  component: OperationsRouteComponent,
})

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'health',
  component: HealthCenterRouteComponent,
})

const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'jobs',
  component: JobsRouteComponent,
})

const billingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'billing',
  component: BillingRouteComponent,
})

// Proxy center route kept for deep links only (not in primary nav)
const proxyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'proxy',
  component: ProxyCenterRouteComponent,
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

const accountProxyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/proxy',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="proxy" />,
})

const accountRiskRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/risk',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="risk" />,
})

const accountDebugRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/debug',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountWorkspaceRouteComponent section="debug" />,
})

const routeTree = rootRoute.addChildren([
  homeRoute,
  accountsRoute,
  accountAddRoute,
  settingsRoute,
  authBatchRoute,
  operationsRoute,
  healthRoute,
  jobsRoute,
  billingRoute,
  proxyRoute,
  accountRoute,
  accountProfileRoute,
  accountJobsRoute,
  accountStoriesRoute,
  accountMusicRoute,
  accountProxyRoute,
  accountRiskRoute,
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
