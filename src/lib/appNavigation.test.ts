import { describe, expect, it } from 'vitest'

import {
  accountListTabFromView,
  resolveInitialNavigationState,
  resolvePopNavigationState,
  resolveTopLevelNavigationTarget,
} from '@/lib/appNavigation'

describe('app navigation boundaries', () => {
  it('starts on dashboard when cached dashboard state exists', () => {
    expect(
      resolveInitialNavigationState({
        hasInitialDashboard: true,
        hasInitialAccountId: true,
        initialView: 'settings',
      }),
    ).toEqual({ phase: 'dashboard', accountListView: 'settings' })
  })

  it('starts batch auth from URL without selecting batch as account-list tab', () => {
    expect(
      resolveInitialNavigationState({
        hasInitialDashboard: false,
        hasInitialAccountId: false,
        initialView: 'auth-batch',
      }),
    ).toEqual({ phase: 'auth-batch', accountListView: 'accounts' })
  })

  it('maps top-level tabs to phases and visible account-list tab', () => {
    expect(resolveTopLevelNavigationTarget('settings')).toEqual({
      phase: 'account-list',
      accountListView: 'settings',
    })
    expect(resolveTopLevelNavigationTarget('auth-batch')).toEqual({
      phase: 'auth-batch',
      accountListView: 'accounts',
    })
  })

  it('resolves popstate only when no account is selected', () => {
    expect(resolvePopNavigationState({ hasAccountId: true, nextView: 'settings' })).toBeNull()
    expect(resolvePopNavigationState({ hasAccountId: false, nextView: 'settings' })).toEqual({
      phase: 'account-list',
      accountListView: 'settings',
    })
    expect(resolvePopNavigationState({ hasAccountId: false, nextView: 'auth-batch' })).toEqual({
      phase: 'auth-batch',
      accountListView: 'accounts',
    })
  })

  it('keeps only accounts and settings visible as account-list tabs', () => {
    expect(accountListTabFromView('accounts')).toBe('accounts')
    expect(accountListTabFromView('settings')).toBe('settings')
    expect(accountListTabFromView('auth-batch')).toBe('accounts')
  })
})
