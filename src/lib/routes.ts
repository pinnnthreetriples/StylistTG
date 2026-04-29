import type { AccountListView } from '@/lib/appView'

export type AppRouteName = 'accounts' | 'settings' | 'auth-batch' | 'account-profile'

export function accountListRoute(view: AccountListView = 'accounts'): string {
  if (view === 'accounts') return '/'
  return `/?view=${encodeURIComponent(view)}`
}

export function accountProfileRoute(accountId: string): string {
  return `/?account_id=${encodeURIComponent(accountId)}`
}

export const appRoutes = {
  accounts: () => accountListRoute('accounts'),
  settings: () => accountListRoute('settings'),
  authBatch: () => accountListRoute('auth-batch'),
  accountProfile: accountProfileRoute,
} as const
