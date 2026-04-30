/**
 * DashboardHeader – sticky top navigation bar for the profile editor.
 *
 * Extracted from App.tsx to keep the main file thin.
 */

import { ArrowLeft, RefreshCw } from 'lucide-react'
import {
  activeCooldownLabels,
  capabilitySummaryLabel,
  healthStatusLabel,
  riskLevelLabel,
  safetyTone,
  validityAgeLabel,
  validityStatusLabel,
  type AccountSafety,
} from '@/lib/accountSafety'
import { proxyStatusLabel, proxyStatusTone, type AccountProxy } from '@/lib/proxy'

interface DashboardHeaderProps {
  displayName: string | null | undefined
  username: string | null | undefined
  isExecutionUsable: boolean
  isBootRefreshing: boolean
  isLoading: boolean
  isRefreshingRuntime: boolean
  isCheckingValidity: boolean
  safety: AccountSafety | null
  proxy: AccountProxy | null
  onBack: () => void
  onRefresh: () => void
  onCheckValidity: () => void
}

export function DashboardHeader({
  displayName,
  username,
  isExecutionUsable,
  isBootRefreshing,
  isLoading,
  isRefreshingRuntime,
  isCheckingValidity,
  safety,
  proxy,
  onBack,
  onRefresh,
  onCheckValidity,
}: DashboardHeaderProps) {
  const statusLabel = safety ? healthStatusLabel(safety.health_status) : isExecutionUsable ? 'Подключено' : 'Требует внимания'
  const safetyStatusTone = safety ? safetyTone(safety.health_status) : isExecutionUsable ? 'green' : 'amber'
  const proxyTone = proxyStatusTone(proxy?.status ?? safety?.proxy_status)
  const cooldownLabels = activeCooldownLabels(safety)
  const safetyDetails = cooldownLabels.length > 0 ? cooldownLabels.join(' · ') : capabilitySummaryLabel(safety)
  const statusClasses = {
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-honey-50 text-honey-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-gray-100 text-gray-500',
  }[safetyStatusTone]

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
            {safety ? (
              <div className="hidden max-w-sm rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] text-gray-500 lg:block">
                <span className="font-medium text-gray-700">{riskLevelLabel(safety.overall_risk_level)}</span>
                <span className="mx-1 text-gray-300">·</span>
                <span>{safetyDetails}</span>
                <span className="mx-1 text-gray-300">·</span>
                <span title={validityStatusLabel(safety.last_validity_check)}>{validityAgeLabel(safety.last_validity_check)}</span>
              </div>
            ) : null}
            <span
              className={`hidden rounded-lg px-2.5 py-1 text-[11px] font-medium lg:inline-flex ${
                {
                  green: 'bg-emerald-50 text-emerald-700',
                  amber: 'bg-honey-50 text-honey-700',
                  red: 'bg-red-50 text-red-600',
                  gray: 'bg-gray-100 text-gray-500',
                }[proxyTone]
              }`}
              title="Proxy используется для сетевой маршрутизации аккаунта и диагностики подключения."
            >
              {proxyStatusLabel(proxy?.status ?? safety?.proxy_status)}
            </span>
            <button
              onClick={onCheckValidity}
              className="hidden items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium text-gray-500 transition-all hover:bg-gray-100 hover:text-gray-700 sm:flex"
            >
              <RefreshCw className={`size-4 ${isCheckingValidity ? 'animate-spin' : ''}`} />
              <span>Проверить</span>
            </button>
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
