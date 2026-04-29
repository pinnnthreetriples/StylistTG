/* eslint-disable react-refresh/only-export-components */
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  redirect,
  useParams,
} from '@tanstack/react-router'

import App from '@/App'
import { queryClient } from '@/lib/queryClient'
import {
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  settingsBundleQueryOptions,
} from '@/lib/queries'
import { resolveLegacyQueryRoute, type AccountWorkspaceSection } from '@/lib/routes'

function AccountRouteComponent({ section }: { section: AccountWorkspaceSection }) {
  const { accountId } = useParams({ strict: false }) as { accountId: string }
  return <App key={`account:${accountId}`} route={{ screen: 'account', accountId, section }} />
}

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
  component: () => <App route={{ screen: 'accounts' }} />,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'settings',
  loader: () => queryClient.ensureQueryData(settingsBundleQueryOptions()),
  component: () => <App route={{ screen: 'settings' }} />,
})

const authBatchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'auth/batch',
  component: () => <App route={{ screen: 'auth-batch' }} />,
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
  component: () => <AccountRouteComponent section="profile" />,
})

const accountProfileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/profile',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountRouteComponent section="profile" />,
})

const accountJobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/jobs',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountRouteComponent section="jobs" />,
})

const accountStoriesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/stories',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountRouteComponent section="stories" />,
})

const accountMusicRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/music',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountRouteComponent section="music" />,
})

const accountDebugRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'accounts/$accountId/debug',
  loader: ({ params }) => loadAccountWorkspace(params.accountId),
  component: () => <AccountRouteComponent section="debug" />,
})

const routeTree = rootRoute.addChildren([
  accountsRoute,
  settingsRoute,
  authBatchRoute,
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
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
