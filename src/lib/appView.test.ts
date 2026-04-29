import { describe, expect, it } from 'vitest'

import { resolveAccountListView, shouldIgnoreStoredAccountForView } from '@/lib/appView'

describe('resolveAccountListView', () => {
  it('keeps accounts as the safe default', () => {
    expect(resolveAccountListView(null)).toBe('accounts')
    expect(resolveAccountListView('missing')).toBe('accounts')
  })

  it('resolves supported account-list views', () => {
    expect(resolveAccountListView('settings')).toBe('settings')
    expect(resolveAccountListView('auth-batch')).toBe('auth-batch')
  })

  it('ignores stored account only for explicit top-level views without account_id', () => {
    expect(shouldIgnoreStoredAccountForView('?view=settings')).toBe(true)
    expect(shouldIgnoreStoredAccountForView('?view=auth-batch')).toBe(true)
    expect(shouldIgnoreStoredAccountForView('?view=settings&account_id=acc-1')).toBe(false)
    expect(shouldIgnoreStoredAccountForView('?tab=profile')).toBe(false)
  })
})
