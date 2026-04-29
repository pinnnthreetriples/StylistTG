export type AccountListView = 'accounts' | 'settings' | 'auth-batch'

export function resolveAccountListView(value: string | null | undefined): AccountListView {
  return value === 'settings' || value === 'auth-batch' ? value : 'accounts'
}

export function readAccountListView(search: string): AccountListView {
  return resolveAccountListView(new URLSearchParams(search).get('view'))
}

export function shouldIgnoreStoredAccountForView(search: string): boolean {
  const params = new URLSearchParams(search)
  return params.has('view') && !params.has('account_id')
}

export function writeAccountListView(view: AccountListView, mode: 'push' | 'replace' = 'push'): void {
  const url = new URL(window.location.href)
  if (view === 'accounts') {
    url.searchParams.delete('view')
  } else {
    url.searchParams.set('view', view)
  }
  const method = mode === 'replace' ? window.history.replaceState : window.history.pushState
  method.call(window.history, {}, '', url)
}
