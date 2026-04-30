import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { createAccountSafetyOverride, deleteAccount, runAccountValidityCheck } from '@/lib/api'
import {
  accountSafetyQueryOptions,
  accountSafetySummaryQueryOptions,
  accountValidityChecksQueryOptions,
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  invalidateAccountSafetyQueries,
  removeAccountSafetyFromCache,
  removeAccountFromAccountsCache,
  removeAccountScopedQueries,
  settingsBundleQueryOptions,
  updateAccountSafetyAfterValidityCheck,
} from '@/lib/queries'

export function useAccountsQuery() {
  return useQuery(accountsQueryOptions())
}

export function useAccountSafetySummaryQuery() {
  return useQuery(accountSafetySummaryQueryOptions())
}

export function useAccountSafetyQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountSafetyQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useAccountValidityChecksQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountValidityChecksQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useRunAccountValidityCheckMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => runAccountValidityCheck(accountId, 'tdlib_readonly'),
    onSuccess: (result, accountId) => {
      updateAccountSafetyAfterValidityCheck(queryClient, accountId, result)
      invalidateAccountSafetyQueries(queryClient, accountId)
    },
  })
}

export function useCreateAccountSafetyOverrideMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      accountId,
      operation,
      reason,
      requestedBlockers,
    }: {
      accountId: string
      operation: string
      reason: string
      requestedBlockers: string[]
    }) =>
      createAccountSafetyOverride(accountId, {
        operation,
        reason,
        requested_blockers: requestedBlockers,
      }),
    onSuccess: (_result, variables) => {
      invalidateAccountSafetyQueries(queryClient, variables.accountId)
    },
  })
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
      void queryClient.prefetchQuery(accountSafetyQueryOptions(accountId))
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
      removeAccountSafetyFromCache(queryClient, accountId)
    },
  })
}
