import {
  Plus,
  Sparkles,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { AccountsTable } from '@/features/accounts/AccountsTable'
import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { SettingsPanel } from '@/components/dashboard/accounts/SettingsPanel'
import {
  useAccountSafetySummaryQuery,
  useAccountsQuery,
  usePrefetchAccountWorkspace,
  usePrefetchSettingsBundle,
  useProxySummaryQuery,
} from '@/hooks/queries/useAccountsQueries'
import {
  type AccountListItem,
  type AccountReadinessRisk,
  type AccountReadinessRiskSummary,
} from '@/lib/api'
import { accountBatchSafetyPreviewQueryOptions, accountRiskSummaryQueryOptions, settingsBundleQueryOptions } from '@/lib/queries'
import {
  type AccountSafetySummary,
} from '@/lib/accountSafety'
import type { AccountProxySummary } from '@/lib/proxy'
import {
  accountMatchesAdvancedFilter,
  accountMatchesFilter,
  accountMatchesSearch,
  accountStats,
  type AccountAdvancedFilter,
  type AccountFilter,
} from '@/lib/accounts'
import { DeleteAccountDialog, EmptyAccounts } from './AccountListLifecycle'
import { SearchAndFilters } from './AccountListFilters'
import { AccountRow, FooterCounter } from './AccountListRows'
import { BatchSafetySummary, RiskSummaryRow, StatsRow } from './AccountListSummary'

const EMPTY_ACCOUNTS: AccountListItem[] = []

function headerRuntimeStatus(preflight: { overall_status: string; rq_worker_status?: string | null } | null | undefined) {
  if (!preflight) {
    return {
      label: 'Проверяем готовность',
      className: 'bg-muted text-muted-foreground',
      dotClassName: 'bg-foreground',
    }
  }
  if (preflight.overall_status === 'ok' && preflight.rq_worker_status === 'ready') {
    return {
      label: 'Live-инфраструктура готова',
      className: 'bg-muted text-primary',
      dotClassName: 'bg-muted',
    }
  }
  if (preflight.rq_worker_status === 'missing') {
    return {
      label: 'Worker не запущен',
      className: 'bg-destructive/10 text-destructive',
      dotClassName: 'bg-destructive',
    }
  }
  return {
    label: 'Live-инфраструктура ограничена',
    className: 'bg-muted text-muted-foreground',
    dotClassName: 'bg-muted',
  }
}

export function AccountList({
  onAddBatch,
  onSelectAccount,
  activeTab,
  onTabChange,
}: {
  onAddBatch: () => void
  onSelectAccount: (accountId: string) => void
  activeTab: 'accounts' | 'settings'
  onTabChange: (tab: 'accounts' | 'settings') => void
}) {
  const accountsQuery = useAccountsQuery()
  const safetySummaryQuery = useAccountSafetySummaryQuery()
  const proxySummaryQuery = useProxySummaryQuery()
  const accountRiskSummaryQuery = useQuery(accountRiskSummaryQueryOptions())
  const prefetchSettingsBundle = usePrefetchSettingsBundle()
  const prefetchAccountWorkspace = usePrefetchAccountWorkspace()
  const accounts = accountsQuery.data ?? EMPTY_ACCOUNTS
  const safetyByAccount = useMemo(
    () => new Map((safetySummaryQuery.data ?? []).map((item) => [item.account_id, item])),
    [safetySummaryQuery.data],
  )
  const proxyByAccount = useMemo(
    () => new Map((proxySummaryQuery.data ?? []).map((item) => [item.account_id, item])),
    [proxySummaryQuery.data],
  )
  const riskByAccount = useMemo(
    () =>
      new Map(
        (accountRiskSummaryQuery.data?.items ?? []).map((risk) => [risk.account_id, risk]),
      ),
    [accountRiskSummaryQuery.data],
  )
  const riskSummary = accountRiskSummaryQuery.data ?? EMPTY_ACCOUNT_RISK_SUMMARY
  const batchSafetyQuery = useQuery(accountBatchSafetyPreviewQueryOptions(accounts.map((account) => account.account_id), 'batch_operation'))
  const settingsBundleQuery = useQuery(settingsBundleQueryOptions())
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const visibleAccountsError =
    accountsError ?? (accountsQuery.isError && !accountsQuery.data ? 'Не удалось загрузить список аккаунтов' : null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<AccountFilter>('all')
  const [advancedFilter, setAdvancedFilter] = useState<AccountAdvancedFilter>('all')
  const [deleteCandidate, setDeleteCandidate] = useState<AccountListItem | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function reloadAccounts() {
    setAccountsError(null)
    try {
      await accountsQuery.refetch()
    } catch {
      setAccountsError('Не удалось загрузить список аккаунтов')
    }
  }

  useEffect(() => {
    if (accountsQuery.isSuccess) {
      prefetchSettingsBundle()
    }
  }, [accountsQuery.isSuccess, prefetchSettingsBundle])

  const stats = useMemo(() => accountStats(accounts), [accounts])
  const visibleAccounts = useMemo(
    () =>
      accounts.filter(
        (account) =>
          accountMatchesFilter(account, filter) &&
          accountMatchesAdvancedFilter(account, safetyByAccount.get(account.account_id), advancedFilter) &&
          accountMatchesSearch(account, query),
      ),
    [accounts, advancedFilter, filter, query, safetyByAccount],
  )

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card">
        <div className="mx-auto max-w-5xl px-5">
          <div className="flex h-14 items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-lg bg-primary">
                <Sparkles className="size-3.5 text-primary-foreground" />
              </div>
              <span className="hidden font-sans text-base font-bold tracking-tight text-foreground min-[380px]:inline">
                StylistTG
              </span>
            </div>

            <div className="mx-1 hidden h-5 w-px bg-muted sm:block" />

            <nav className="flex h-full items-center gap-6">
              <button
                className={`h-full border-b-2 pt-0.5 text-sm font-medium transition-all ${
                  activeTab === 'accounts'
                    ? 'border-border text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => onTabChange('accounts')}
                type="button"
              >
                Аккаунты
              </button>
              <button
                className={`h-full border-b-2 pt-0.5 text-sm font-medium transition-all ${
                  activeTab === 'settings'
                    ? 'border-border text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => onTabChange('settings')}
                type="button"
              >
                Настройки
              </button>
            </nav>

            <div className="ml-auto flex items-center gap-2.5">
              <span className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 sm:flex ${headerRuntimeStatus(settingsBundleQuery.data?.preflight).className}`}>
                <span className={`size-1.5 animate-pulse rounded-full ${headerRuntimeStatus(settingsBundleQuery.data?.preflight).dotClassName}`} />
                <span className="text-[11px] font-medium">{headerRuntimeStatus(settingsBundleQuery.data?.preflight).label}</span>
              </span>
              <button
                aria-label="Добавить аккаунты"
                className="flex items-center gap-1.5 rounded-lg bg-primary px-2.5 py-1.5 text-[13px] font-medium text-primary-foreground sm:px-3.5"
                onClick={onAddBatch}
                type="button"
              >
                <Plus className="size-4" />
                <span className="hidden sm:inline">Добавить аккаунты</span>
                <span className="hidden min-[380px]:inline sm:hidden">Добавить</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 pb-10 pt-5">
        {activeTab === 'settings' ? (
          <SettingsPanel />
        ) : (
          <AccountsContent
            accounts={visibleAccounts}
            allAccounts={accounts}
            error={visibleAccountsError}
            filter={filter}
            isLoading={accountsQuery.isPending && !accountsQuery.data}
            onAddBatch={onAddBatch}
            advancedFilter={advancedFilter}
            onFilterChange={setFilter}
            onAdvancedFilterChange={setAdvancedFilter}
            onQueryChange={setQuery}
            onReload={() => void reloadAccounts()}
            onRequestDelete={(account) => {
              setDeleteError(null)
              setDeleteCandidate(account)
            }}
            onPrefetchAccount={(accountId) => {
              prefetchAccountWorkspace(accountId)
            }}
            onSelectAccount={onSelectAccount}
            query={query}
            safetyByAccount={safetyByAccount}
            proxyByAccount={proxyByAccount}
            batchSafety={batchSafetyQuery.data ?? null}
            stats={stats}
            riskByAccount={riskByAccount}
            riskSummary={riskSummary}
          />
        )}
      </main>

      {deleteCandidate ? (
        <DeleteAccountDialog
          account={deleteCandidate}
          error={deleteError}
          onCancel={() => {
            setDeleteCandidate(null)
            setDeleteError(null)
          }}
          onError={setDeleteError}
          onSubmitted={() => {
            setDeleteCandidate(null)
            setDeleteError(null)
          }}
        />
      ) : null}
    </div>
  )
}

function AccountsContent({
  accounts,
  allAccounts,
  error,
  filter,
  advancedFilter,
  isLoading,
  onAddBatch,
  onFilterChange,
  onAdvancedFilterChange,
  onQueryChange,
  onReload,
  onRequestDelete,
  onPrefetchAccount,
  onSelectAccount,
  query,
  safetyByAccount,
  proxyByAccount,
  batchSafety,
  stats,
  riskByAccount,
  riskSummary,
}: {
  accounts: AccountListItem[]
  allAccounts: AccountListItem[]
  error: string | null
  filter: AccountFilter
  advancedFilter: AccountAdvancedFilter
  isLoading: boolean
  onAddBatch: () => void
  onFilterChange: (filter: AccountFilter) => void
  onAdvancedFilterChange: (filter: AccountAdvancedFilter) => void
  onQueryChange: (query: string) => void
  onReload: () => void
  onRequestDelete: (account: AccountListItem) => void
  onPrefetchAccount: (accountId: string) => void
  onSelectAccount: (accountId: string) => void
  query: string
  safetyByAccount: Map<string, AccountSafetySummary>
  proxyByAccount: Map<string, AccountProxySummary>
  batchSafety: { counts: Record<string, number>; can_start: boolean } | null
  stats: ReturnType<typeof accountStats>
  riskByAccount: Map<string, AccountReadinessRisk>
  riskSummary: AccountReadinessRiskSummary
}) {
  if (isLoading) {
    return (
      <section className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground shadow-sm">
        Загружаем аккаунты...
      </section>
    )
  }

  if (error) {
    return (
      <section className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="text-sm font-semibold text-muted-foreground">{error}</div>
        <button
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          onClick={onReload}
          type="button"
        >
          Повторить
        </button>
      </section>
    )
  }

  if (allAccounts.length === 0) {
    return <EmptyAccounts onAddBatch={onAddBatch} />
  }

  return (
    <>
      <StatsRow stats={stats} />
      <RiskSummaryRow summary={riskSummary} />
      {batchSafety ? <BatchSafetySummary counts={batchSafety.counts} canStart={batchSafety.can_start} /> : null}
      <SearchAndFilters
        filter={filter}
        onFilterChange={onFilterChange}
        onAdvancedFilterChange={onAdvancedFilterChange}
        onQueryChange={onQueryChange}
        query={query}
        advancedFilter={advancedFilter}
        stats={stats}
      />

      {accounts.length > 0 ? (
        <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          {accounts.map((account, index) => (
            <AccountRow
              account={account}
              index={index}
              isLast={index === accounts.length - 1}
              key={account.account_id}
              onPrefetchAccount={onPrefetchAccount}
              onRequestDelete={onRequestDelete}
              onSelectAccount={onSelectAccount}
              proxy={proxyByAccount.get(account.account_id) ?? null}
              safety={safetyByAccount.get(account.account_id) ?? null}
            />
          ))}
        </section>
      ) : (
        <section className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground shadow-sm">
          Ничего не найдено.
        </section>
      )}

      <section className="mt-5 rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="mb-3">
          <h2 className="text-sm font-bold text-foreground">Таблица аккаунтов</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            TanStack Table view for sorting, selection, and column visibility migration.
          </p>
        </div>
        <AccountsTable accounts={accounts} onSelectAccount={onSelectAccount} riskByAccount={riskByAccount} />
      </section>

      <FooterCounter stats={stats} />
    </>
  )
}

