import type { WarmupEvent, WarmupStatus } from './types'

export const WARMUP_STATUS_LABELS: Record<WarmupStatus, string> = {
  draft: 'Черновик',
  validating: 'Проверка',
  scheduled: 'Запланирована',
  active: 'Идёт подготовка',
  paused_risk: 'Пауза по риску',
  paused_manual: 'Пауза',
  completed: 'Завершена',
  failed: 'Ошибка',
}

export const WARMUP_EVENT_LABELS: Record<string, string> = {
  session_created: 'Сессия создана',
  task_executed: 'Шаг выполнен',
  task_skipped: 'Шаг пропущен',
  day_advanced: 'День обновлён',
  completed: 'Подготовка завершена',
  paused: 'Пауза включена',
  resumed: 'Подготовка возобновлена',
  queue_enqueue_failed: 'Очередь недоступна',
  circuit_breaker_triggered: 'Защита остановила сессию',
}

export function formatWarmupEventPayload(event: WarmupEvent): string {
  if (event.event_type === 'session_created') return 'Сессия поставлена в расписание. Live-действия не выполняются.'
  if (event.event_type === 'task_executed') return `Dry-run шаг записан: день ${String(event.payload.day ?? '-')}.`
  if (event.event_type === 'day_advanced') return `Следующий день подготовки: ${String(event.payload.day ?? '-')}.`
  if (event.event_type === 'paused') return `Причина: ${String(event.payload.reason ?? 'ручная пауза')}.`
  if (event.event_type === 'resumed') return 'Сессия вернулась в расписание.'
  if (event.event_type === 'completed') return '14-дневный план завершён.'
  if (event.event_type === 'queue_enqueue_failed') return 'Сессия остановлена, потому что задача не попала в RQ.'
  return JSON.stringify(event.payload)
}

export function formatWarmupDate(value: string | null): string {
  if (!value) return 'Не запланирован'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWarmupNextStep(value: string | null, workersEnabled: boolean | undefined): string {
  if (!value) return 'Не запланирован'
  if (new Date(value).getTime() <= Date.now()) {
    return workersEnabled ? 'Готов к шагу сейчас' : 'Ждёт включения воркера'
  }
  return formatWarmupDate(value)
}

export function warmupProgressPercent(day: number): number {
  return Math.min(100, Math.max(0, Math.round((day / 14) * 100)))
}
