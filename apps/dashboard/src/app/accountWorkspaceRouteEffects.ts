import type { AppRouteState } from '@/lib/routes'

export type AccountRouteState = Extract<AppRouteState, { screen: 'account' }>

export function workspaceSectionIdForSection(
  section: AccountRouteState['section'],
): string | null {
  if (section === 'profile') return null
  if (section === 'jobs') return 'account-workspace-jobs'
  if (section === 'debug') return 'account-workspace-debug'
  return `account-workspace-${section}`
}

function sameWorkspaceRoute(
  previousRoute: AccountRouteState | null,
  nextRoute: AccountRouteState,
): boolean {
  return (
    previousRoute?.accountId === nextRoute.accountId &&
    previousRoute.section === nextRoute.section
  )
}

export function shouldResetWorkspaceSectionState(
  previousRoute: AccountRouteState | null,
  nextRoute: AccountRouteState,
): boolean {
  return !sameWorkspaceRoute(previousRoute, nextRoute)
}
