import type { AccountListView } from '@/lib/appView'
import type { AuthPhase } from '@/lib/auth'

export type AccountListTab = 'accounts' | 'settings'

export type NavigationState = {
  phase: AuthPhase
  accountListView: AccountListTab
}

export function accountListTabFromView(view: AccountListView): AccountListTab {
  return view === 'settings' ? 'settings' : 'accounts'
}

export function resolveInitialNavigationState({
  hasInitialAccountId,
  hasInitialDashboard,
  initialView,
}: {
  hasInitialAccountId: boolean
  hasInitialDashboard: boolean
  initialView: AccountListView
}): NavigationState {
  if (hasInitialDashboard) {
    return { phase: 'dashboard', accountListView: accountListTabFromView(initialView) }
  }
  if (hasInitialAccountId) {
    return { phase: 'auth-loading', accountListView: accountListTabFromView(initialView) }
  }
  if (initialView === 'auth-batch') {
    return { phase: 'auth-batch', accountListView: 'accounts' }
  }
  return { phase: 'account-list', accountListView: accountListTabFromView(initialView) }
}

export function resolveTopLevelNavigationTarget(view: AccountListView): NavigationState {
  if (view === 'auth-batch') {
    return { phase: 'auth-batch', accountListView: 'accounts' }
  }
  return { phase: 'account-list', accountListView: accountListTabFromView(view) }
}

export function resolvePopNavigationState({
  hasAccountId,
  nextView,
}: {
  hasAccountId: boolean
  nextView: AccountListView
}): NavigationState | null {
  if (hasAccountId) return null
  return resolveTopLevelNavigationTarget(nextView)
}
