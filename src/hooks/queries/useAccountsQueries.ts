import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { deleteAccount } from '@/lib/api'
import {
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  removeAccountFromAccountsCache,
  removeAccountScopedQueries,
  settingsBundleQueryOptions,
} from '@/lib/queries'

export function useAccountsQuery() {
  return useQuery(accountsQueryOptions())
}

export function usePrefetchSettingsBundle() {
  const queryClient = useQueryClient()
  return useCallback(() => {
    void queryClient.prefetchQuery(settingsBundleQueryOptions())
  }, [queryClient])
}

export function usePrefetchAccountWorkspace() {
  const queryClient = useQueryClient()
  return useCallback(
    (accountId: string) => {
      void queryClient.prefetchQuery(authStateQueryOptions(accountId))
      void queryClient.prefetchQuery(dashboardBundleQueryOptions(accountId))
    },
    [queryClient],
  )
}

export function useDeleteAccountMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: (_result, accountId) => {
      removeAccountFromAccountsCache(queryClient, accountId)
      removeAccountScopedQueries(queryClient, accountId)
    },
  })
}
