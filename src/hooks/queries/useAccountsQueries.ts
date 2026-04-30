import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import {
  checkAccountProxy,
  createAccountSafetyOverride,
  deleteAccount,
  deleteAccountProxy,
  runAccountValidityCheck,
  saveAccountProxy,
} from '@/lib/api'
import {
  accountOperationLogsQueryOptions,
  accountProxyQueryOptions,
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
  proxySummaryQueryOptions,
  queryKeys,
} from '@/lib/queries'
import type { AccountProxyInput } from '@/lib/proxy'

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

export function useProxySummaryQuery() {
  return useQuery(proxySummaryQueryOptions())
}

export function useAccountProxyQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountProxyQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useAccountOperationLogsQuery(accountId: string | null | undefined, limit = 50) {
  return useQuery({
    ...accountOperationLogsQueryOptions(accountId ?? '', limit),
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

export function useSaveAccountProxyMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, payload }: { accountId: string; payload: AccountProxyInput }) =>
      saveAccountProxy(accountId, payload),
    onSuccess: (result, variables) => {
      queryClient.setQueryData(queryKeys.proxy.account(variables.accountId), result)
      void queryClient.invalidateQueries({ queryKey: queryKeys.proxy.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.operationLogs.account(variables.accountId) })
    },
  })
}

export function useCheckAccountProxyMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => checkAccountProxy(accountId),
    onSuccess: (result, accountId) => {
      queryClient.setQueryData(queryKeys.proxy.account(accountId), result)
      void queryClient.invalidateQueries({ queryKey: queryKeys.proxy.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.operationLogs.account(accountId) })
    },
  })
}

export function useDeleteAccountProxyMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => deleteAccountProxy(accountId),
    onSuccess: (_result, accountId) => {
      queryClient.setQueryData(queryKeys.proxy.account(accountId), null)
      void queryClient.invalidateQueries({ queryKey: queryKeys.proxy.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.summary })
      void queryClient.invalidateQueries({ queryKey: queryKeys.operationLogs.account(accountId) })
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
      void queryClient.prefetchQuery(accountProxyQueryOptions(accountId))
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
