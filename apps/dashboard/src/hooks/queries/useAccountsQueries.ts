import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import {
  checkAccountProxy,
  createAccountDeletionRequest,
  createAccountExportRequest,
  createAccountSafetyOverride,
  deleteAccountProxy,
  runAccountValidityCheck,
  saveAccountProxy,
} from '@/lib/api'
import {
  accountOperationLogsQueryOptions,
  accountRiskQueryOptions,
  accountProxyQueryOptions,
  accountDeletionPreviewQueryOptions,
  accountDeletionRequestsQueryOptions,
  accountExportRequestsQueryOptions,
  accountAuditEventsQueryOptions,
  accountCooldownsQueryOptions,
  actionGateQueryOptions,
  accountSafetyQueryOptions,
  accountSafetySummaryQueryOptions,
  accountValidityChecksQueryOptions,
  accountsQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  invalidateAccountSafetyQueries,
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

export function useAccountRiskQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountRiskQueryOptions(accountId ?? ''),
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

export function useAccountDeletionPreviewQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountDeletionPreviewQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useAccountDeletionRequestsQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountDeletionRequestsQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useAccountExportRequestsQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountExportRequestsQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useAccountAuditEventsQuery(accountId: string | null | undefined, limit = 50) {
  return useQuery({
    ...accountAuditEventsQueryOptions(accountId ?? '', limit),
    enabled: Boolean(accountId),
  })
}

export function useAccountCooldownsQuery(accountId: string | null | undefined) {
  return useQuery({
    ...accountCooldownsQueryOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  })
}

export function useActionGateQuery(accountId: string | null | undefined, actionType: string) {
  return useQuery({
    ...actionGateQueryOptions(accountId ?? '', actionType),
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

export function useCreateAccountDeletionRequestMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      accountId,
      reason,
      dryRun,
    }: {
      accountId: string
      reason: string
      dryRun: boolean
    }) =>
      createAccountDeletionRequest(accountId, {
        reason,
        confirmation: 'DELETE',
        dry_run: dryRun,
      }),
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accountLifecycle.deletionRequests(variables.accountId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit.account(variables.accountId) })
    },
  })
}

export function useCreateAccountExportRequestMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => createAccountExportRequest(accountId),
    onSuccess: (_result, accountId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accountLifecycle.exportRequests(accountId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit.account(accountId) })
    },
  })
}
