import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FlaskConical,
  Loader2,
  Plus,
  Search,
  Server,
  Sparkles,
  Trash2,
  X,
  UserRound,
  Users,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import type React from 'react'
import { AccountsTable } from '@/features/accounts/AccountsTable'
import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { SettingsPanel } from '@/components/dashboard/accounts/SettingsPanel'
import {
  useAccountAuditEventsQuery,
  useAccountCooldownsQuery,
  useAccountDeletionPreviewQuery,
  useAccountDeletionRequestsQuery,
  useAccountExportRequestsQuery,
  useAccountSafetySummaryQuery,
  useAccountsQuery,
  useActionGateQuery,
  useCreateAccountDeletionRequestMutation,
  useCreateAccountExportRequestMutation,
  usePrefetchAccountWorkspace,
  usePrefetchSettingsBundle,
  useProxySummaryQuery,
} from '@/hooks/queries/useAccountsQueries'
import {
  buildAssetContentUrl,
  type AccountListItem,
  type AccountReadinessRisk,
  type AccountReadinessRiskSummary,
  type AccountDeletionPreview,
} from '@/lib/api'
import { accountBatchSafetyPreviewQueryOptions, accountRiskSummaryQueryOptions, settingsBundleQueryOptions } from '@/lib/queries'
import {
  compactSafetyReasons,
  activeCooldownLabels,
  compactSafetyStatusLabel,
  compactSafetyTone,
  riskLevelLabel,
  type AccountSafetySummary,
} from '@/lib/accountSafety'
import { proxyStatusLabel, proxyStatusTone, type AccountProxySummary } from '@/lib/proxy'
import {
  accountMatchesAdvancedFilter,
  accountMatchesFilter,
  accountMatchesSearch,
  accountStats,
  accountStatus,
  maskPhone,
  type AccountAdvancedFilter,
  type AccountFilter,
} from '@/lib/accounts'

const filterLabels: Record<AccountFilter, string> = {
  all: 'Все',
  authorized: 'Авторизованы',
  waiting: 'Ожидают',
  error: 'Ошибки',
}

const advancedFilterLabels: Record<AccountAdvancedFilter, string> = {
  all: 'Любая готовность',
  safety_ready: 'Готовы',
  needs_login: 'Нужен вход',
  paused: 'На паузе',
  limited: 'Ограничения',
  unchecked: 'Не проверены',
}

const EMPTY_ACCOUNTS: AccountListItem[] = []

function headerRuntimeStatus(preflight: { overall_status: string; rq_worker_status?: string | null } | null | undefined) {
  if (!preflight) {
    return {
      label: 'Проверяем готовность',
      className: 'bg-gray-50 text-gray-600',
      dotClassName: 'bg-gray-400',
    }
  }
  if (preflight.overall_status === 'ok' && preflight.rq_worker_status === 'ready') {
    return {
      label: 'Live-инфраструктура готова',
      className: 'bg-emerald-50 text-emerald-700',
      dotClassName: 'bg-emerald-500',
    }
  }
  if (preflight.rq_worker_status === 'missing') {
    return {
      label: 'Worker не запущен',
      className: 'bg-red-50 text-red-700',
      dotClassName: 'bg-red-500',
    }
  }
  return {
    label: 'Live-инфраструктура ограничена',
    className: 'bg-amber-50 text-amber-700',
    dotClassName: 'bg-amber-500',
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
    <div className="min-h-screen bg-cream">
      <header className="sticky top-0 z-40 border-b border-gray-200/70 bg-white">
        <div className="mx-auto max-w-5xl px-5">
          <div className="flex h-14 items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-lg bg-navy-400">
                <Sparkles className="size-3.5 text-white" />
              </div>
              <span className="hidden font-display text-base font-bold tracking-tight text-navy-900 min-[380px]:inline">
                StylistTG
              </span>
            </div>

            <div className="mx-1 hidden h-5 w-px bg-gray-200 sm:block" />

            <nav className="flex h-full items-center gap-6">
              <button
                className={`h-full border-b-2 pt-0.5 text-sm font-medium transition-all ${
                  activeTab === 'accounts'
                    ? 'border-navy-400 text-navy-900'
                    : 'border-transparent text-gray-500 hover:text-gray-900'
                }`}
                onClick={() => onTabChange('accounts')}
                type="button"
              >
                Аккаунты
              </button>
              <button
                className={`h-full border-b-2 pt-0.5 text-sm font-medium transition-all ${
                  activeTab === 'settings'
                    ? 'border-navy-400 text-navy-900'
                    : 'border-transparent text-gray-500 hover:text-gray-900'
                }`}
                onClick={() => onTabChange('settings')}
                type="button"
              >
                Настройки
              </button>
            </nav>

            <div className="ml-auto flex items-center gap-2.5">
              <span className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 sm:flex ${headerRuntimeStatus(settingsBundleQuery.data?.preflight).className}`}>
                <span className={`size-1.5 animate-pulse-dot rounded-full ${headerRuntimeStatus(settingsBundleQuery.data?.preflight).dotClassName}`} />
                <span className="text-[11px] font-medium">{headerRuntimeStatus(settingsBundleQuery.data?.preflight).label}</span>
              </span>
              <button
                aria-label="Добавить аккаунты"
                className="add-btn flex items-center gap-1.5 rounded-lg bg-navy-400 px-2.5 py-1.5 text-[13px] font-medium text-white sm:px-3.5"
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
      <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center text-sm text-gray-500 shadow-sm">
        Загружаем аккаунты...
      </section>
    )
  }

  if (error) {
    return (
      <section className="fade-in rounded-xl border border-rose-100 bg-white p-8 text-center shadow-sm">
        <div className="text-sm font-semibold text-rose-600">{error}</div>
        <button
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-navy-400 px-4 py-2 text-sm font-semibold text-white"
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
        <section className="fade-in overflow-hidden rounded-xl border border-gray-200/70 bg-white shadow-soft">
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
        <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center text-sm text-gray-500 shadow-sm">
          Ничего не найдено.
        </section>
      )}

      <section className="fade-in d12 mt-5 rounded-xl border border-gray-200/70 bg-white p-4 shadow-soft">
        <div className="mb-3">
          <h2 className="text-sm font-bold text-navy-900">Таблица аккаунтов</h2>
          <p className="mt-1 text-xs text-gray-500">
            TanStack Table view for sorting, selection, and column visibility migration.
          </p>
        </div>
        <AccountsTable accounts={accounts} onSelectAccount={onSelectAccount} riskByAccount={riskByAccount} />
      </section>

      <FooterCounter stats={stats} />
    </>
  )
}

function StatsRow({ stats }: { stats: ReturnType<typeof accountStats> }) {
  return (
    <div className="fade-in mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard icon={<Users className="size-4 text-navy-400" />} label="Всего" value={stats.total} />
      <StatCard
        icon={<CheckCircle2 className="size-4 text-emerald-500" />}
        label="Авторизованы"
        tone="emerald"
        value={stats.authorized}
      />
      <StatCard
        icon={<Clock className="size-4 text-honey-500" />}
        label="Ожидают"
        tone="honey"
        value={stats.waiting}
      />
      <StatCard
        icon={<AlertCircle className="size-4 text-tangerine-400" />}
        label="Ошибки"
        tone="tangerine"
        value={stats.error}
      />
    </div>
  )
}

function RiskSummaryRow({ summary }: { summary: AccountReadinessRiskSummary }) {
  return (
    <section className="fade-in mb-4 rounded-xl border border-gray-200/70 bg-white px-4 py-3 shadow-soft">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-navy-900">Риск аккаунтов</div>
        <div className="text-[11px] font-semibold text-gray-500">app-known readiness score</div>
      </div>
      <div className="grid gap-2 sm:grid-cols-4">
        <RiskMetric label="Низкий" value={summary.low} className="bg-emerald-50 text-emerald-700" />
        <RiskMetric label="Средний" value={summary.medium} className="bg-honey-50 text-honey-700" />
        <RiskMetric label="Высокий" value={summary.high} className="bg-orange-50 text-orange-700" />
        <RiskMetric label="Критический" value={summary.critical} className="bg-red-50 text-red-700" />
      </div>
    </section>
  )
}


function RiskMetric({ className, label, value }: { className: string; label: string; value: number }) {
  return (
    <div className={`rounded-lg px-3 py-2 text-xs font-semibold ${className}`}>
      <div>{label}</div>
      <div className="mt-1 text-lg font-bold">{value}</div>
    </div>
  )
}

function BatchSafetySummary({
  counts,
  canStart,
}: {
  counts: Record<string, number>
  canStart: boolean
}) {
  const items = [
    ['Готовы', counts.ready ?? 0, 'text-emerald-700 bg-emerald-50'],
    ['Нужен вход', counts.needs_login ?? 0, 'text-red-700 bg-red-50'],
    ['На паузе', counts.paused ?? 0, 'text-honey-700 bg-honey-50'],
    ['Ограничения', counts.limited ?? 0, 'text-tangerine-700 bg-tangerine-50'],
    ['Неизвестно', counts.unknown ?? 0, 'text-gray-600 bg-gray-100'],
  ] as const
  return (
    <section className="fade-in mb-4 rounded-xl border border-gray-200/70 bg-white px-4 py-3 shadow-soft">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-navy-900">Готовность массовых действий</div>
        <div className={`text-[11px] font-semibold ${canStart ? 'text-emerald-700' : 'text-honey-700'}`}>
          {canStart ? 'Можно запускать' : 'Есть ограничения'}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map(([label, value, className]) => (
          <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${className}`} key={label}>
            {label}: {value}
          </span>
        ))}
      </div>
    </section>
  )
}

function StatCard({
  icon,
  label,
  tone = 'navy',
  value,
}: {
  icon: React.ReactNode
  label: string
  tone?: 'navy' | 'emerald' | 'honey' | 'tangerine'
  value: number
}) {
  const color = {
    navy: 'text-navy-900 bg-navy-50',
    emerald: 'text-emerald-600 bg-emerald-50',
    honey: 'text-honey-600 bg-honey-50',
    tangerine: 'text-tangerine-500 bg-tangerine-50',
  }[tone]

  return (
    <div className="stat-card flex items-center gap-3 rounded-xl border border-gray-200/70 bg-white px-4 py-3">
      <div className={`flex size-9 items-center justify-center rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className={`text-lg font-bold leading-none ${tone === 'navy' ? 'text-navy-900' : color.split(' ')[0]}`}>
          {value}
        </p>
        <p className="mt-0.5 text-[11px] text-gray-400">{label}</p>
      </div>
    </div>
  )
}

function SearchAndFilters({
  advancedFilter,
  filter,
  onAdvancedFilterChange,
  onFilterChange,
  onQueryChange,
  query,
  stats,
}: {
  advancedFilter: AccountAdvancedFilter
  filter: AccountFilter
  onAdvancedFilterChange: (filter: AccountAdvancedFilter) => void
  onFilterChange: (filter: AccountFilter) => void
  onQueryChange: (query: string) => void
  query: string
  stats: ReturnType<typeof accountStats>
}) {
  const counts: Record<AccountFilter, number> = {
    all: stats.total,
    authorized: stats.authorized,
    waiting: stats.waiting,
    error: stats.error,
  }

  return (
    <div className="fade-in d1 mb-4 grid gap-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative max-w-sm flex-1">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
        <input
          className="search-field w-full rounded-lg border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm transition-all"
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Поиск аккаунтов..."
          type="text"
          value={query}
        />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(filterLabels) as AccountFilter[]).map((item) => (
            <button
              className={`chip rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-all ${
                filter === item
                  ? 'border-navy-200 bg-navy-50 text-navy-400'
                  : 'border-gray-200 text-gray-500 hover:bg-gray-50'
              }`}
              key={item}
              onClick={() => onFilterChange(item)}
              type="button"
            >
              {filterLabels[item]} <span className="ml-1 opacity-60">{counts[item]}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {(Object.keys(advancedFilterLabels) as AccountAdvancedFilter[]).map((item) => (
          <button
            className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition-all ${
              advancedFilter === item
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-gray-200 text-gray-500 hover:bg-gray-50'
            }`}
            key={item}
            onClick={() => onAdvancedFilterChange(item)}
            type="button"
          >
            {advancedFilterLabels[item]}
          </button>
        ))}
      </div>
    </div>
  )
}

function AccountRow({
  account,
  index,
  isLast,
  onSelectAccount,
  onPrefetchAccount,
  onRequestDelete,
  safety,
  proxy,
}: {
  account: AccountListItem
  index: number
  isLast: boolean
  onSelectAccount: (accountId: string) => void
  onPrefetchAccount: (accountId: string) => void
  onRequestDelete: (account: AccountListItem) => void
  safety: AccountSafetySummary | null
  proxy: AccountProxySummary | null
}) {
  const status = accountStatus(account)
  const name = account.display_name || account.phone_number
  const initial = name.slice(0, 1).toUpperCase()
  const statusStyle = statusStyles[status.kind]
  const StatusIcon = statusStyle.icon

  return (
    <div
      className={`account-row fade-in d${Math.min(index + 2, 12)} group flex w-full items-center gap-3.5 px-4 py-3 text-left transition-all ${
        isLast ? '' : 'border-b border-gray-100'
      } ${status.kind === 'error' ? 'bg-tangerine-50/30' : ''}`}
    >
      <button
        className="flex min-w-0 flex-1 items-center gap-3.5 text-left"
        onFocus={() => onPrefetchAccount(account.account_id)}
        onMouseEnter={() => onPrefetchAccount(account.account_id)}
        onClick={() => onSelectAccount(account.account_id)}
        type="button"
      >
        <AccountAvatar account={account} fallbackClassName={avatarGradient(index)} initial={initial} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-navy-900">{name}</p>
            <span className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${statusStyle.badge}`}>
              <StatusIcon className="size-2.5" />
              {status.label}
            </span>
            {account.is_test_dc ? (
              <span className="inline-flex shrink-0 items-center gap-1 rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-600">
                <FlaskConical className="size-2.5" />
                Test DC
              </span>
            ) : null}
            <SafetyBadge safety={safety} />
            <ProxyBadge proxy={proxy} />
          </div>
          <p className={`mt-0.5 truncate text-xs ${status.kind === 'error' ? 'text-tangerine-400' : 'text-gray-400'}`}>
            {account.username ? `@${account.username} · ` : ''}
            {maskPhone(account.phone_number)}
          </p>
          {safety ? (
            <p className="mt-0.5 truncate text-[11px] text-gray-400">
              {accountSafetyDetails(safety)}
            </p>
          ) : null}
        </div>
      </button>
      <div className="flex shrink-0 items-center gap-2">
        <span className={`hidden text-[11px] lg:inline ${statusStyle.detail}`}>
          {status.kind === 'authorized' ? updatedAgo(account.updated_at) : status.detail}
        </span>
        <button
          aria-label={`Удалить аккаунт ${name}`}
          className="flex size-8 items-center justify-center rounded-lg text-gray-300 transition-all hover:bg-red-50 hover:text-red-500"
          onClick={() => onRequestDelete(account)}
          title="Удалить аккаунт"
          type="button"
        >
          <Trash2 className="size-4" />
        </button>
        <ChevronRight className="row-chevron size-5 text-gray-300 transition-all group-hover:translate-x-0.5 group-hover:text-navy-400" />
      </div>
    </div>
  )
}

function ProxyBadge({ proxy }: { proxy: AccountProxySummary | null }) {
  const tone = proxyStatusTone(proxy?.status)
  const classes = {
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-honey-50 text-honey-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-gray-100 text-gray-500',
  }[tone]
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}
      title="Proxy используется для сетевой маршрутизации аккаунта и диагностики подключения."
    >
      {proxyStatusLabel(proxy?.status)}
    </span>
  )
}

function SafetyBadge({ safety }: { safety: AccountSafetySummary | null }) {
  if (!safety) return null
  const tone = compactSafetyTone(safety)
  const classes = {
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-honey-50 text-honey-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-gray-100 text-gray-500',
  }[tone]

  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}>
      {compactSafetyStatusLabel(safety)}
    </span>
  )
}

function accountSafetyDetails(safety: AccountSafetySummary): string {
  const cooldowns = activeCooldownLabels(safety)
  if (cooldowns.length > 0) return cooldowns.join(' · ')
  return compactSafetyReasons(safety).join(' · ') || riskLevelLabel(safety.overall_risk_level)
}

function AccountAvatar({
  account,
  fallbackClassName,
  initial,
}: {
  account: AccountListItem
  fallbackClassName: string
  initial: string
}) {
  const [failedAssetId, setFailedAssetId] = useState<string | null>(null)

  if (account.profile_photo_asset_id && failedAssetId !== account.profile_photo_asset_id) {
    return (
      <img
        alt=""
        className="size-10 shrink-0 rounded-full object-cover"
        onError={() => setFailedAssetId(account.profile_photo_asset_id)}
        src={buildAssetContentUrl(account.profile_photo_asset_id)}
      />
    )
  }

  return (
    <div className={`flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${fallbackClassName}`}>
      {initial}
    </div>
  )
}

const statusStyles = {
  authorized: {
    icon: Check,
    badge: 'bg-emerald-50 text-emerald-700',
    detail: 'text-gray-400',
  },
  waiting: {
    icon: Clock,
    badge: 'bg-honey-50 text-honey-600',
    detail: 'text-honey-500',
  },
  error: {
    icon: AlertTriangle,
    badge: 'bg-red-50 text-red-600',
    detail: 'text-tangerine-400',
  },
}

function avatarGradient(index: number): string {
  const gradients = [
    'bg-gradient-to-br from-navy-400 to-navy-300',
    'bg-gradient-to-br from-tangerine-400 to-honey-400',
    'bg-gradient-to-br from-emerald-400 to-emerald-300',
    'bg-gradient-to-br from-honey-400 to-honey-300',
    'bg-gradient-to-br from-violet-400 to-violet-300',
    'bg-gradient-to-br from-rose-400 to-rose-300',
    'bg-gradient-to-br from-cyan-400 to-cyan-300',
    'bg-gradient-to-br from-indigo-400 to-indigo-300',
  ]
  return gradients[index % gradients.length]
}

function updatedAgo(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return 'Недавно'

  const diffMinutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000))
  if (diffMinutes < 1) return 'Сейчас'
  if (diffMinutes < 60) return `${diffMinutes} мин. назад`

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} ч назад`
  return `${Math.round(diffHours / 24)} дн назад`
}

function FooterCounter({ stats }: { stats: ReturnType<typeof accountStats> }) {
  return (
    <div className="fade-in d12 mt-4 flex flex-col gap-2 px-1 text-xs text-gray-400 sm:flex-row sm:items-center sm:justify-between">
      <p>
        Всего: <span className="font-medium text-gray-500">{stats.total} аккаунтов</span>
        <span className="mx-1.5 text-gray-300">·</span>
        <span className="font-medium text-emerald-600">{stats.authorized} авторизованы</span>
        <span className="mx-1.5 text-gray-300">·</span>
        <span className="font-medium text-honey-500">{stats.waiting} ожидают</span>
        <span className="mx-1.5 text-gray-300">·</span>
        <span className="font-medium text-tangerine-400">{stats.error} ошибки</span>
      </p>
      <div className="flex items-center gap-1">
        <Server className="size-3.5" />
        TDLib · FastAPI · RQ · PostgreSQL
      </div>
    </div>
  )
}

function EmptyAccounts({ onAddBatch }: { onAddBatch: () => void }) {
  return (
    <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center shadow-sm">
      <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-navy-50">
        <UserRound className="size-5 text-navy-400" />
      </div>
      <h1 className="mt-4 font-display text-xl font-bold tracking-tight text-navy-900">
        Аккаунтов пока нет
      </h1>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-gray-500">
        Добавьте один или несколько Telegram-аккаунтов, чтобы открыть редактор профиля и запускать задачи.
      </p>
      <button
        className="add-btn mt-5 inline-flex items-center gap-1.5 rounded-lg bg-navy-400 px-4 py-2 text-sm font-semibold text-white"
        onClick={onAddBatch}
        type="button"
      >
        <Plus className="size-4" />
        Добавить аккаунты
      </button>
    </section>
  )
}

function DeleteAccountDialog({
  account,
  error,
  onCancel,
  onError,
  onSubmitted,
}: {
  account: AccountListItem
  error: string | null
  onCancel: () => void
  onError: (message: string | null) => void
  onSubmitted: () => void
}) {
  const name = account.display_name || account.phone_number
  const previewQuery = useAccountDeletionPreviewQuery(account.account_id)
  const deletionRequestsQuery = useAccountDeletionRequestsQuery(account.account_id)
  const exportRequestsQuery = useAccountExportRequestsQuery(account.account_id)
  const auditEventsQuery = useAccountAuditEventsQuery(account.account_id, 8)
  const cooldownsQuery = useAccountCooldownsQuery(account.account_id)
  const actionGateQuery = useActionGateQuery(account.account_id, 'account.delete')
  const deletionRequestMutation = useCreateAccountDeletionRequestMutation()
  const exportRequestMutation = useCreateAccountExportRequestMutation()
  const [reason, setReason] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const isSubmitting = deletionRequestMutation.isPending
  const preview = previewQuery.data
  const canSubmit =
    confirmation === 'DELETE' &&
    reason.trim().length >= 10 &&
    preview?.can_delete !== false &&
    !isSubmitting

  async function submitDeletionRequest() {
    onError(null)
    if (!canSubmit) return
    try {
      await deletionRequestMutation.mutateAsync({
        accountId: account.account_id,
        dryRun: true,
        reason: reason.trim(),
      })
      onSubmitted()
    } catch {
      onError('Не удалось создать заявку на удаление. Проверьте preview, reason и confirmation.')
    }
  }

  async function requestExport() {
    onError(null)
    try {
      await exportRequestMutation.mutateAsync(account.account_id)
    } catch {
      onError('Не удалось создать export request.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/20 px-4 backdrop-animate">
      <div className="modal-animate max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <div>
            <h2 className="font-display text-base font-bold text-navy-900">Account lifecycle request</h2>
            <p className="mt-0.5 text-xs text-gray-400">{name}</p>
          </div>
          <button
            aria-label="Закрыть подтверждение удаления"
            className="flex size-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="max-h-[68vh] overflow-y-auto px-5 py-4">
          <p className="text-sm leading-6 text-gray-600">
            Удаление теперь проходит через auditable lifecycle request. По умолчанию создаётся safe dry-run request:
            backend фиксирует preview, reason и audit event без live TDLib действий.
          </p>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <LifecycleCard title="Risk gate">
              <div className="text-xs text-gray-600">
                {actionGateQuery.data ? (
                  <>
                    <div className="font-semibold text-navy-900">
                      {actionGateQuery.data.allowed ? 'Allowed' : 'Blocked'} · {actionGateQuery.data.risk_level} · {actionGateQuery.data.risk_score}
                    </div>
                    <div className="mt-1">{actionGateQuery.data.requires_override ? 'Override reason required.' : 'No override required for this request.'}</div>
                  </>
                ) : actionGateQuery.isError ? (
                  'Risk gate unavailable.'
                ) : (
                  'Checking risk gate...'
                )}
              </div>
            </LifecycleCard>
            <LifecycleCard title="Cooldowns">
              <CompactList
                empty="No active cooldowns."
                items={(cooldownsQuery.data ?? []).map((cooldown) => `${cooldown.operation}: ${cooldown.reason_code}`)}
                loading={cooldownsQuery.isPending}
              />
            </LifecycleCard>
          </div>

          <LifecycleCard className="mt-3" title="Deletion preview">
            {previewQuery.isPending ? (
              <div className="text-xs text-gray-500">Loading deletion preview...</div>
            ) : previewQuery.isError ? (
              <div className="text-xs font-semibold text-red-600">Deletion preview unavailable.</div>
            ) : preview ? (
              <DeletionPreview preview={preview} />
            ) : null}
          </LifecycleCard>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <LifecycleCard title="Export data">
              <button
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-navy-700 hover:bg-gray-50 disabled:opacity-60"
                disabled={exportRequestMutation.isPending}
                onClick={() => void requestExport()}
                type="button"
              >
                {exportRequestMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Server className="size-3.5" />}
                Request export
              </button>
              <CompactList
                empty="No export requests yet."
                items={(exportRequestsQuery.data ?? []).slice(0, 3).map((item) => `${item.status} · ${formatLifecycleTime(item.requested_at)}`)}
                loading={exportRequestsQuery.isPending}
              />
            </LifecycleCard>
            <LifecycleCard title="Audit history">
              <CompactList
                empty="No audit events yet."
                items={(auditEventsQuery.data?.items ?? []).slice(0, 4).map((item) => `${item.action} · ${formatLifecycleTime(item.created_at)}`)}
                loading={auditEventsQuery.isPending}
              />
            </LifecycleCard>
          </div>

          <LifecycleCard className="mt-3" title="Deletion request">
            <label className="grid gap-1 text-xs font-semibold text-gray-600">
              Reason
              <textarea
                className="min-h-20 rounded-lg border border-gray-200 px-3 py-2 text-sm font-normal text-navy-900 outline-none focus:border-navy-300"
                onChange={(event) => setReason(event.target.value)}
                placeholder="Describe why this account lifecycle request is required..."
                value={reason}
              />
            </label>
            <label className="mt-3 grid gap-1 text-xs font-semibold text-gray-600">
              Confirmation
              <input
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-normal text-navy-900 outline-none focus:border-navy-300"
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="Type DELETE"
                value={confirmation}
              />
            </label>
            <CompactList
              empty="No deletion requests yet."
              items={(deletionRequestsQuery.data ?? []).slice(0, 3).map((item) => `${item.status} · ${formatLifecycleTime(item.requested_at)}`)}
              loading={deletionRequestsQuery.isPending}
            />
          </LifecycleCard>

          {error ? (
            <div className="mt-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs font-medium text-red-600">
              {error}
            </div>
          ) : null}
        </div>
        <div className="flex items-center justify-end gap-2 bg-gray-50 px-5 py-4">
          <button
            className="rounded-lg px-3.5 py-2 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            Отмена
          </button>
          <button
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3.5 py-2 text-sm font-semibold text-white transition-all hover:bg-red-600 disabled:opacity-60"
            disabled={!canSubmit}
            onClick={() => void submitDeletionRequest()}
            type="button"
          >
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            Create request
          </button>
        </div>
      </div>
    </div>
  )
}

function LifecycleCard({
  children,
  className = '',
  title,
}: {
  children: React.ReactNode
  className?: string
  title: string
}) {
  return (
    <section className={`rounded-xl border border-gray-200/70 bg-gray-50/60 p-3 ${className}`}>
      <h3 className="text-xs font-bold uppercase tracking-wide text-gray-500">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  )
}

function CompactList({ empty, items, loading }: { empty: string; items: string[]; loading: boolean }) {
  if (loading) return <div className="mt-2 text-xs text-gray-500">Loading...</div>
  if (items.length === 0) return <div className="mt-2 text-xs text-gray-500">{empty}</div>
  return (
    <ul className="mt-2 grid gap-1 text-xs text-gray-600">
      {items.map((item) => (
        <li className="truncate rounded-lg bg-white px-2 py-1" key={item}>
          {item}
        </li>
      ))}
    </ul>
  )
}

function DeletionPreview({ preview }: { preview: AccountDeletionPreview }) {
  return (
    <div className="text-xs text-gray-600">
      <div className={`font-semibold ${preview.can_delete ? 'text-emerald-700' : 'text-red-600'}`}>
        {preview.can_delete ? 'Request can be created' : 'Blocked'} · risk {preview.risk_level}
      </div>
      {preview.blocking_reasons.length > 0 ? (
        <ul className="mt-2 grid gap-1 text-red-600">
          {preview.blocking_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-2 grid gap-1">
        {preview.planned_actions.map((action, index) => (
          <div className="rounded-lg bg-white px-2 py-1" key={`${action.type}-${action.resource}-${index}`}>
            {action.resource}: {plannedActionDetail(action)}
          </div>
        ))}
      </div>
    </div>
  )
}

function plannedActionDetail(action: AccountDeletionPreview['planned_actions'][number]): string {
  if (typeof action.count === 'number') return `${action.count} item(s)`
  if (typeof action.present === 'boolean') return action.present ? 'present' : 'not present'
  return action.retention_policy ?? 'planned'
}

function formatLifecycleTime(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Date(timestamp).toLocaleString()
}
