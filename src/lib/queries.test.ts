import { describe, expect, it } from 'vitest'

import { queryClient } from '@/lib/queryClient'
import {
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  queryKeys,
  settingsBundleQueryOptions,
} from '@/lib/queries'

describe('query cache configuration', () => {
  it('keeps server state warm long enough for fast tab navigation', () => {
    expect(queryClient.getDefaultOptions().queries).toMatchObject({
      staleTime: 30_000,
      gcTime: 20 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    })
  })

  it('uses stable query keys for settings, accounts and dashboard tabs', () => {
    expect(accountsQueryOptions().queryKey).toEqual(queryKeys.accounts)
    expect(authStateQueryOptions('account-1').queryKey).toEqual(['authState', 'account-1'])
    expect(settingsBundleQueryOptions().queryKey).toEqual(['settings', 'bundle'])
    expect(dashboardBundleQueryOptions('account-1').queryKey).toEqual([
      'dashboard',
      'account-1',
      'bundle',
    ])
  })
})
