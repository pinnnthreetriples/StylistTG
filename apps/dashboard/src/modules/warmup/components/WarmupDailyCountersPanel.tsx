/**
 * Phase 1 · daily counters table.
 *
 * Сравнивает фактические `daily_counters` из текущей сессии с лимитами
 * `daily_action_limits` стратегии (если они известны). Это даёт оператору
 * точный «сколько действий уже сделано из плана» без необходимости лезть
 * в `warmup_event` журнал.
 */
import { SectionCard } from '@stylisttg/ui'

import type { WarmupDailyCounters, WarmupDailyLimits, WarmupStrategy } from '../types'

const FALLBACK_ACTION_TYPES = ['feed_read', 'join_chat', 'p2p_send'] as const

export function WarmupDailyCountersPanel({
  currentDay,
  durationDays,
  dailyCounters,
  strategy,
}: {
  currentDay: number
  durationDays: number
  dailyCounters: WarmupDailyCounters
  strategy: WarmupStrategy | null | undefined
}) {
  const planByDay = strategy?.daily_action_limits ?? {}
  const actionTypes = collectActionTypes(planByDay, dailyCounters)
  if (actionTypes.length === 0) {
    return (
      <SectionCard
        title="Действия по дням"
        description="План пока не содержит действий, либо стратегия не использует daily_action_limits."
      >
        <div className="rounded-lg border border-dashed border-border bg-muted px-4 py-6 text-sm text-muted-foreground">
          Журнал событий ниже отражает каждое действие, которое выполнила
          сессия.
        </div>
      </SectionCard>
    )
  }
  const days = buildDayRange(durationDays, currentDay)
  return (
    <SectionCard
      title="Действия по дням"
      description="Слева — план стратегии, справа — фактическое количество выполненных действий."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-left text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="border-b border-border px-2 py-1 font-semibold uppercase">
                День
              </th>
              {actionTypes.map((actionType) => (
                <th
                  key={actionType}
                  className="border-b border-border px-2 py-1 font-semibold uppercase"
                >
                  {actionType}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {days.map((day) => {
              const planKey = String(day + 1)
              const counterKey = String(day)
              const planForDay = (planByDay[planKey] ?? {}) as WarmupDailyLimits
              const countersForDay = (dailyCounters[counterKey] ?? {}) as WarmupDailyLimits
              const isCurrent = day === currentDay
              const isFuture = day > currentDay
              return (
                <tr
                  key={day}
                  className={
                    isCurrent
                      ? 'bg-muted text-muted-foreground'
                      : isFuture
                        ? 'text-muted-foreground'
                        : 'text-foreground'
                  }
                >
                  <td className="border-b border-border px-2 py-1 font-semibold">
                    {day + 1}
                  </td>
                  {actionTypes.map((actionType) => {
                    const planned = planForDay[actionType] ?? 0
                    const actual = countersForDay[actionType] ?? 0
                    return (
                      <td
                        className="border-b border-border px-2 py-1"
                        key={`${day}:${actionType}`}
                      >
                        <span className="font-mono text-[11px]">
                          {actual}
                          <span className="text-muted-foreground">/{planned}</span>
                        </span>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}

function collectActionTypes(
  plan: Record<string, WarmupDailyLimits>,
  counters: WarmupDailyCounters,
): string[] {
  const set = new Set<string>()
  for (const dayPlan of Object.values(plan)) {
    if (!dayPlan) continue
    for (const key of Object.keys(dayPlan)) {
      if (typeof dayPlan[key] === 'number' && dayPlan[key]! > 0) set.add(key)
    }
  }
  for (const dayCounters of Object.values(counters)) {
    if (!dayCounters) continue
    for (const key of Object.keys(dayCounters)) {
      set.add(key)
    }
  }
  if (set.size === 0) return []
  // Stable ordering: prioritize known action types first.
  const sorted = [...set].sort((a, b) => {
    const ai = (FALLBACK_ACTION_TYPES as readonly string[]).indexOf(a)
    const bi = (FALLBACK_ACTION_TYPES as readonly string[]).indexOf(b)
    if (ai === -1 && bi === -1) return a.localeCompare(b)
    if (ai === -1) return 1
    if (bi === -1) return -1
    return ai - bi
  })
  return sorted
}

function buildDayRange(durationDays: number, currentDay: number): number[] {
  const horizon = Math.max(1, durationDays || 1)
  const upper = Math.min(Math.max(currentDay + 1, horizon), horizon)
  const days: number[] = []
  for (let day = 0; day < upper; day += 1) days.push(day)
  return days
}
