import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { fetchWarmupSelectableAccounts } from '../api'
import type { WarmupSelectableAccount } from '../types'
import { AvailableAccountsColumn } from './AvailableAccountsColumn'
import { AccountFiltersBar } from './AccountFiltersBar'
import { addAllAccounts, moveAccount, selectedAccountsFromCache } from './AccountSelectorModel'
import { SelectedAccountsColumn } from './SelectedAccountsColumn'

const EMPTY_SELECTABLE_ACCOUNTS: WarmupSelectableAccount[] = []

export function WarmupAccountSelector({
  accounts: injectedAccounts,
  onSelectionChange,
  selectedAccountIds,
}: {
  accounts?: WarmupSelectableAccount[]
  onSelectionChange: (accountIds: string[]) => void
  selectedAccountIds: string[]
}) {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [country, setCountry] = useState('')
  const [role, setRole] = useState('')
  const [proxyOkOnly, setProxyOkOnly] = useState(false)
  const [hideInWork, setHideInWork] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  const query = useQuery({
    queryKey: ['warmup', 'selectable-accounts', debouncedSearch, country, role, proxyOkOnly, hideInWork] as const,
    queryFn: () =>
      fetchWarmupSelectableAccounts({
        country,
        hideInWork,
        proxyOkOnly,
        role,
        search: debouncedSearch,
      }),
    enabled: injectedAccounts == null,
  })

  const accounts = injectedAccounts ?? query.data ?? EMPTY_SELECTABLE_ACCOUNTS
  const selectedAccounts = selectedAccountsFromCache(selectedAccountIds, accounts)
  const selectedIds = new Set(selectedAccountIds)
  const availableAccounts = accounts.filter((account) => !selectedIds.has(account.account_id))
  const countries = useMemo(() => uniqueSorted(accounts.map((account) => account.country_iso)), [accounts])
  const roles = useMemo(() => uniqueSorted(accounts.map((account) => account.role)), [accounts])

  const addAccount = (accountId: string) => onSelectionChange(moveAccount(selectedAccountIds, accountId, 'add'))
  const removeAccount = (accountId: string) => onSelectionChange(moveAccount(selectedAccountIds, accountId, 'remove'))

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex flex-col gap-2 border-b border-border px-3 py-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold text-foreground">Аккаунты для прогрева</div>
          <div className="text-xs text-muted-foreground">Отфильтровано: {accounts.length} / Всего: {accounts.length}</div>
        </div>
        <div className="text-2xl font-semibold tabular-nums text-foreground">{selectedAccountIds.length}</div>
      </div>
      <AccountFiltersBar
        countries={countries}
        country={country}
        hideInWork={hideInWork}
        proxyOkOnly={proxyOkOnly}
        role={role}
        roles={roles}
        search={search}
        onCountryChange={setCountry}
        onHideInWorkChange={setHideInWork}
        onProxyOkOnlyChange={setProxyOkOnly}
        onRoleChange={setRole}
        onSearchChange={setSearch}
      />
      {query.error ? <div className="border-b border-border px-3 py-2 text-sm text-destructive">Не удалось загрузить аккаунты.</div> : null}
      <div className="grid gap-3 p-3 xl:grid-cols-2">
        <AvailableAccountsColumn
          accounts={availableAccounts}
          filteredCount={accounts.length}
          onAdd={addAccount}
          onAddAll={() => onSelectionChange(addAllAccounts(selectedAccountIds, availableAccounts))}
        />
        <SelectedAccountsColumn accounts={selectedAccounts} onRemove={removeAccount} onRemoveAll={() => onSelectionChange([])} />
      </div>
    </div>
  )
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((left, right) => left.localeCompare(right))
}
