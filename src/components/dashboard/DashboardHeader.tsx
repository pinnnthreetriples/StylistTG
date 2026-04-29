/**
 * DashboardHeader – sticky top navigation bar for the profile editor.
 *
 * Extracted from App.tsx to keep the main file thin.
 */

import { ArrowLeft, RefreshCw } from 'lucide-react'

interface DashboardHeaderProps {
  displayName: string | null | undefined
  username: string | null | undefined
  isExecutionUsable: boolean
  isBootRefreshing: boolean
  isLoading: boolean
  isRefreshingRuntime: boolean
  onBack: () => void
  onRefresh: () => void
}

export function DashboardHeader({
  displayName,
  username,
  isExecutionUsable,
  isBootRefreshing,
  isLoading,
  isRefreshingRuntime,
  onBack,
  onRefresh,
}: DashboardHeaderProps) {
  const statusLabel = isExecutionUsable ? 'Подключено' : 'Требует внимания'
  const statusClasses = isExecutionUsable
    ? 'bg-emerald-50 text-emerald-700'
    : 'bg-honey-50 text-honey-700'

  return (
    <header className="bg-white border-b border-gray-200/70 sticky top-0 z-40">
      {/* Thin refresh progress line */}
      <PageRefreshIndicator active={isBootRefreshing || isLoading} />

      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="flex items-center h-14 gap-3">
          {/* ── Back button ── */}
          <button
            onClick={onBack}
            className="flex items-center gap-1 px-2 py-1.5 -ml-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-all"
          >
            <ArrowLeft className="size-4" />
            <span className="text-sm font-medium hidden sm:inline">Назад</span>
          </button>

          {/* ── Account avatar + name ── */}
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-navy-400 to-tangerine-300 flex items-center justify-center text-white text-[11px] font-bold">
              {displayName?.[0]?.toUpperCase() ?? 'A'}
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-semibold text-gray-800 leading-none">
                {displayName ?? 'Профиль'}
              </p>
              <p className="text-[11px] text-gray-400 leading-none mt-0.5">
                {username ? `@${username}` : ''}
              </p>
            </div>
          </div>

          {/* ── Right controls ── */}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={onRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium text-navy-400 hover:bg-navy-50 rounded-lg transition-all"
            >
              <RefreshCw className={`size-4 ${isRefreshingRuntime ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Синхронизировать</span>
            </button>

            <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${statusClasses}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80 animate-pulse-dot" />
              <span className="text-[11px] font-medium">{statusLabel}</span>
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

/** Animated progress line that appears at the very top of the header during loading. */
function PageRefreshIndicator({ active }: { active: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-transparent">
      <div
        className={`h-full origin-left bg-navy-400 transition-opacity duration-200 ${
          active ? 'animate-page-refresh opacity-100' : 'opacity-0'
        }`}
      />
    </div>
  )
}
