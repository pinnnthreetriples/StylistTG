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
import { useEffect, useMemo, useState } from 'react'
import type React from 'react'
import { SettingsPanel } from '@/components/dashboard/accounts/SettingsPanel'
import {
  useAccountsQuery,
  useDeleteAccountMutation,
  usePrefetchAccountWorkspace,
  usePrefetchSettingsBundle,
} from '@/hooks/queries/useAccountsQueries'
import { buildAssetContentUrl, type AccountListItem } from '@/lib/api'
import {
  accountMatchesFilter,
  accountMatchesSearch,
  accountStats,
  accountStatus,
  maskPhone,
  type AccountFilter,
} from '@/lib/accounts'

const filterLabels: Record<AccountFilter, string> = {
  all: 'Все',
  authorized: 'Авторизованы',
  waiting: 'Ожидают',
  error: 'Ошибки',
}

const EMPTY_ACCOUNTS: AccountListItem[] = []

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
  const deleteAccountMutation = useDeleteAccountMutation()
  const prefetchSettingsBundle = usePrefetchSettingsBundle()
  const prefetchAccountWorkspace = usePrefetchAccountWorkspace()
  const accounts = accountsQuery.data ?? EMPTY_ACCOUNTS
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const visibleAccountsError =
    accountsError ?? (accountsQuery.isError && !accountsQuery.data ? 'Не удалось загрузить список аккаунтов' : null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<AccountFilter>('all')
  const [deleteCandidate, setDeleteCandidate] = useState<AccountListItem | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deletingAccountId, setDeletingAccountId] = useState<string | null>(null)

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
        (account) => accountMatchesFilter(account, filter) && accountMatchesSearch(account, query),
      ),
    [accounts, filter, query],
  )

  async function confirmDeleteAccount() {
    if (!deleteCandidate) return
    setDeletingAccountId(deleteCandidate.account_id)
    setDeleteError(null)
    try {
      await deleteAccountMutation.mutateAsync(deleteCandidate.account_id)
      setDeleteCandidate(null)
    } catch {
      setDeleteError('Не удалось удалить аккаунт. Проверьте, что нет активных задач.')
    } finally {
      setDeletingAccountId(null)
    }
  }

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
              <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 sm:flex">
                <span className="size-1.5 animate-pulse-dot rounded-full bg-emerald-500" />
                <span className="text-[11px] font-medium text-emerald-700">TDLib подключен</span>
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
            onFilterChange={setFilter}
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
            stats={stats}
          />
        )}
      </main>

      {deleteCandidate ? (
        <DeleteAccountDialog
          account={deleteCandidate}
          error={deleteError}
          isDeleting={deletingAccountId === deleteCandidate.account_id}
          onCancel={() => {
            if (deletingAccountId) return
            setDeleteCandidate(null)
            setDeleteError(null)
          }}
          onConfirm={() => void confirmDeleteAccount()}
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
  isLoading,
  onAddBatch,
  onFilterChange,
  onQueryChange,
  onReload,
  onRequestDelete,
  onPrefetchAccount,
  onSelectAccount,
  query,
  stats,
}: {
  accounts: AccountListItem[]
  allAccounts: AccountListItem[]
  error: string | null
  filter: AccountFilter
  isLoading: boolean
  onAddBatch: () => void
  onFilterChange: (filter: AccountFilter) => void
  onQueryChange: (query: string) => void
  onReload: () => void
  onRequestDelete: (account: AccountListItem) => void
  onPrefetchAccount: (accountId: string) => void
  onSelectAccount: (accountId: string) => void
  query: string
  stats: ReturnType<typeof accountStats>
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
      <SearchAndFilters
        filter={filter}
        onFilterChange={onFilterChange}
        onQueryChange={onQueryChange}
        query={query}
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
            />
          ))}
        </section>
      ) : (
        <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center text-sm text-gray-500 shadow-sm">
          Ничего не найдено.
        </section>
      )}

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
  filter,
  onFilterChange,
  onQueryChange,
  query,
  stats,
}: {
  filter: AccountFilter
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
    <div className="fade-in d1 mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
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
  )
}

function AccountRow({
  account,
  index,
  isLast,
  onSelectAccount,
  onPrefetchAccount,
  onRequestDelete,
}: {
  account: AccountListItem
  index: number
  isLast: boolean
  onSelectAccount: (accountId: string) => void
  onPrefetchAccount: (accountId: string) => void
  onRequestDelete: (account: AccountListItem) => void
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
          </div>
          <p className={`mt-0.5 truncate text-xs ${status.kind === 'error' ? 'text-tangerine-400' : 'text-gray-400'}`}>
            {account.username ? `@${account.username} · ` : ''}
            {maskPhone(account.phone_number)}
          </p>
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
  isDeleting,
  onCancel,
  onConfirm,
}: {
  account: AccountListItem
  error: string | null
  isDeleting: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const name = account.display_name || account.phone_number

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/20 px-4 backdrop-animate">
      <div className="modal-animate w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <div>
            <h2 className="font-display text-base font-bold text-navy-900">Удалить аккаунт?</h2>
            <p className="mt-0.5 text-xs text-gray-400">{name}</p>
          </div>
          <button
            aria-label="Закрыть подтверждение удаления"
            className="flex size-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            disabled={isDeleting}
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm leading-6 text-gray-600">
            Аккаунт будет удалён из локального списка вместе с черновиками, историей задач и
            сохранённым состоянием профиля. Активные задачи блокируют удаление.
          </p>
          {error ? (
            <div className="mt-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs font-medium text-red-600">
              {error}
            </div>
          ) : null}
        </div>
        <div className="flex items-center justify-end gap-2 bg-gray-50 px-5 py-4">
          <button
            className="rounded-lg px-3.5 py-2 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            disabled={isDeleting}
            onClick={onCancel}
            type="button"
          >
            Отмена
          </button>
          <button
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3.5 py-2 text-sm font-semibold text-white transition-all hover:bg-red-600 disabled:opacity-60"
            disabled={isDeleting}
            onClick={onConfirm}
            type="button"
          >
            {isDeleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            Удалить
          </button>
        </div>
      </div>
    </div>
  )
}
