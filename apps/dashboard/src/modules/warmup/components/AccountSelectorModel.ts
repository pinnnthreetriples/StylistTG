import type { WarmupSelectableAccount } from '../types'

export function moveAccount(
  selectedIds: string[],
  accountId: string,
  direction: 'add' | 'remove',
): string[] {
  if (direction === 'add') {
    return selectedIds.includes(accountId) ? selectedIds : [...selectedIds, accountId]
  }
  return selectedIds.filter((id) => id !== accountId)
}

export function addAllAccounts(selectedIds: string[], accounts: WarmupSelectableAccount[]): string[] {
  const next = new Set(selectedIds)
  for (const account of accounts) next.add(account.account_id)
  return Array.from(next)
}

export function groupSelectedAccounts(
  accounts: WarmupSelectableAccount[],
): Record<string, WarmupSelectableAccount[]> {
  return accounts.reduce<Record<string, WarmupSelectableAccount[]>>((acc, account) => {
    const country = account.country_iso || 'XX'
    acc[country] = acc[country] ?? []
    acc[country].push(account)
    return acc
  }, {})
}

export function selectedAccountsFromCache(
  selectedIds: string[],
  accounts: WarmupSelectableAccount[],
): WarmupSelectableAccount[] {
  const byId = new Map(accounts.map((account) => [account.account_id, account]))
  return selectedIds.flatMap((id) => {
    const account = byId.get(id)
    return account ? [account] : []
  })
}
