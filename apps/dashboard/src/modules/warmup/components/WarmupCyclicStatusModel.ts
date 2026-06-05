import type { WarmupCycleConfig } from '../types'

export type WarmupCyclicStatusModel = {
  headline: string
  progress: string
  isActive: boolean
}

export function getWarmupCyclicStatusModel(
  cycleConfig: WarmupCycleConfig,
  now: Date,
  timezone?: string | null,
): WarmupCyclicStatusModel {
  const local = getLocalDateTimeParts(now, timezone)
  const isActive = cycleConfig.start_hour <= local.hour && local.hour < cycleConfig.end_hour
  const currentCycle = clamp(cycleConfig.current_cycle, 1, cycleConfig.days_total)
  if (isActive) {
    return {
      headline: `🟢 Активно до ${formatWarmupCycleHour(cycleConfig.end_hour)}`,
      isActive: true,
      progress: `День ${currentCycle} из ${cycleConfig.days_total}`,
    }
  }
  const startsTomorrow = local.hour >= cycleConfig.end_hour
  return {
    headline: `⏸ Ожидаются активные часы — старт в ${formatWarmupCycleHour(cycleConfig.start_hour)} ${
      startsTomorrow ? 'завтра' : 'сегодня'
    }`,
    isActive: false,
    progress: `День ${currentCycle} из ${cycleConfig.days_total}`,
  }
}

export function formatWarmupCycleHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

function getLocalDateTimeParts(now: Date, timezone?: string | null): { hour: number } {
  const formatter = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    hour12: false,
    timeZone: timezone || 'UTC',
  })
  const hour = Number(formatter.formatToParts(now).find((part) => part.type === 'hour')?.value ?? '0')
  return { hour: hour === 24 ? 0 : hour }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}
