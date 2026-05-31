import type { QueryClient } from '@tanstack/react-query'

import { type AccountListItem, updateWorkspaceSafetyPolicy } from '@/lib/api'
import type { AccountSafety, AccountSafetySummary, AccountValidityCheck } from '@/lib/accountSafety'

import { queryKeys } from './queryKeys'
import type { SettingsBundle } from './queryTypes'

export function removeAccountScopedQueries(queryClient: QueryClient, accountId: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.dashboard.account(accountId) })
  queryClient.removeQueries({ queryKey: queryKeys.authState(accountId), exact: true })
}

export function invalidateAccountSafetyQueries(queryClient: QueryClient, accountId: string): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.summary })
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.account(accountId), exact: true })
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.checks(accountId), exact: true })
}

export function updateAccountSafetyAfterValidityCheck(
  queryClient: QueryClient,
  accountId: string,
  check: AccountValidityCheck,
): void {
  queryClient.setQueryData<AccountSafety | undefined>(queryKeys.accountSafety.account(accountId), (current) =>
    current ? { ...current, last_validity_check: check, validity_status: String(check.result?.validity_status ?? current.validity_status) } : current,
  )
  queryClient.setQueryData<AccountValidityCheck[] | undefined>(queryKeys.accountSafety.checks(accountId), (current) => {
    const existing = current ?? []
    return [check, ...existing.filter((item) => item.id !== check.id)].slice(0, 10)
  })
}

export function removeAccountSafetyFromCache(queryClient: QueryClient, accountId: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.accountSafety.account(accountId), exact: true })
  queryClient.removeQueries({ queryKey: queryKeys.accountSafety.checks(accountId), exact: true })
  queryClient.setQueryData(queryKeys.accountSafety.summary, (current: AccountSafetySummary[] | undefined) =>
    (current ?? []).filter((safety) => safety.account_id !== accountId),
  )
}


export function removeAccountFromAccountsCache(queryClient: QueryClient, accountId: string): void {
  queryClient.setQueryData(queryKeys.accounts, (current: AccountListItem[] | undefined) =>
    (current ?? []).filter((account) => account.account_id !== accountId),
  )
}

export function updateSettingsPolicyInCache(queryClient: QueryClient, policy: SettingsBundle['policy']): void {
  queryClient.setQueryData(queryKeys.settings.bundle, (current: SettingsBundle | undefined) =>
    current ? { ...current, policy } : current,
  )
}

export function updateSettingsAuthModeInCache(queryClient: QueryClient, authMode: SettingsBundle['authMode']): void {
  queryClient.setQueryData(queryKeys.settings.bundle, (current: SettingsBundle | undefined) =>
    current ? { ...current, authMode } : current,
  )
}

export function updateWorkspaceSafetyPolicyInCache(
  queryClient: QueryClient,
  policy: Awaited<ReturnType<typeof updateWorkspaceSafetyPolicy>>,
): void {
  queryClient.setQueryData(queryKeys.settings.safetyPolicy, policy)
}
