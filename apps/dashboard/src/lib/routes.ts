export type AccountWorkspaceSection = 'profile' | 'jobs' | 'stories' | 'music' | 'proxy' | 'risk' | 'debug'

export type AppRouteState =
  | { screen: 'accounts' }
  | { screen: 'settings' }
  | { screen: 'auth-batch' }
  | { screen: 'operations' }
  | { screen: 'health' }
  | { screen: 'jobs' }
  | { screen: 'warmup' }
  | { screen: 'proxy' }
  | { screen: 'account'; accountId: string; section: AccountWorkspaceSection }

export type AppRouteName =
  | 'accounts'
  | 'settings'
  | 'auth-batch'
  | 'operations'
  | 'health'
  | 'jobs'
  | 'warmup'
  | 'proxy'
  | 'account'
  | 'account-profile'
  | 'account-jobs'
  | 'account-stories'
  | 'account-music'
  | 'account-proxy'
  | 'account-risk'
  | 'account-debug'

export function accountListRoute(): string {
  return '/accounts'
}

export function accountAddRoute(): string {
  return '/accounts/add'
}

export function accountProfileRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/profile`
}

export function accountRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}`
}

export function accountJobsRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/jobs`
}

export function accountStoriesRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/stories`
}

export function accountMusicRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/music`
}

export function accountProxyRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/proxy`
}

export function accountRiskRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/risk`
}

export function accountDebugRoute(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/debug`
}

export const appRoutes = {
  accounts: accountListRoute,
  accountAdd: accountAddRoute,
  settings: () => '/settings',
  authBatch: accountAddRoute,
  operations: () => '/operations',
  health: () => '/health',
  jobs: () => '/jobs',
  warmup: () => '/modules/warmup',
  proxy: () => '/proxy',
  login: () => '/login',
  account: accountRoute,
  accountProfile: accountProfileRoute,
  accountJobs: accountJobsRoute,
  accountStories: accountStoriesRoute,
  accountMusic: accountMusicRoute,
  accountProxy: accountProxyRoute,
  accountRisk: accountRiskRoute,
  accountDebug: accountDebugRoute,
} as const

export function accountWorkspaceRoute(accountId: string, section: AccountWorkspaceSection): string {
  if (section === 'profile') return appRoutes.accountProfile(accountId)
  if (section === 'jobs') return appRoutes.accountJobs(accountId)
  if (section === 'stories') return appRoutes.accountStories(accountId)
  if (section === 'music') return appRoutes.accountMusic(accountId)
  if (section === 'proxy') return appRoutes.accountProxy(accountId)
  if (section === 'risk') return appRoutes.accountRisk(accountId)
  return appRoutes.accountDebug(accountId)
}

export function resolveLegacyQueryRoute(search: string): string | null {
  const params = new URLSearchParams(search)
  const accountId = params.get('account_id')
  if (accountId) return appRoutes.account(accountId)

  const view = params.get('view')
  if (view === 'settings') return appRoutes.settings()
  if (view === 'auth-batch') return appRoutes.authBatch()

  return null
}
