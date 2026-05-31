import { Search } from 'lucide-react'

import { accountStats, type AccountAdvancedFilter, type AccountFilter } from '@/lib/accounts'

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

export function SearchAndFilters({
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
    <div className="mb-4 grid gap-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative max-w-sm flex-1">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          aria-label="Поиск аккаунтов"
          className="search-field w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm transition-all"
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
                  ? 'border-border bg-muted text-primary'
                  : 'border-border text-muted-foreground hover:bg-muted'
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
                ? 'border-border bg-muted text-primary'
                : 'border-border text-muted-foreground hover:bg-muted'
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
