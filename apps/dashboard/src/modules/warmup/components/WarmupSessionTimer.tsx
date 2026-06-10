import { Badge } from '@stylisttg/ui'

import { useWarmupSessionTimer } from '../hooks'
import type { WarmupSessionTimer as WarmupSessionTimerData } from '../types'
import { formatTimerText, useElapsedSeconds } from './WarmupSessionTimerModel'

type WarmupSessionTimerProps = {
  sessionId: string | null
  timer?: WarmupSessionTimerData
  now?: Date
}

export function WarmupSessionTimer({ sessionId, timer, now }: WarmupSessionTimerProps) {
  const query = useWarmupSessionTimer(timer ? null : sessionId)
  const data = timer ?? query.data ?? null
  const elapsedSeconds = useElapsedSeconds(data, now)

  if (!data) {
    return (
      <div className="rounded-lg border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
        Таймер прогрева пока недоступен.
      </div>
    )
  }

  const totalSeconds = Math.max(1, data.total_duration_seconds)
  const clampedElapsed = Math.min(totalSeconds, Math.max(0, elapsedSeconds))
  const progress = Math.min(1, Math.max(0, clampedElapsed / totalSeconds))
  const isComplete = clampedElapsed >= totalSeconds

  return (
    <section className="rounded-lg border border-border bg-card px-3 py-2" aria-label="Прогресс по времени">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">⏱ Прогресс по времени</span>
          <Badge tone={timerStatusTone(data.status)}>{timerStatusLabel(data.status)}</Badge>
        </div>
        <span className="font-mono text-sm font-semibold text-foreground">
          {formatTimerText(clampedElapsed, totalSeconds)}
          {isComplete ? ' ✓' : ''}
        </span>
      </div>
      <progress className="sr-only" max={100} value={Math.round(progress * 100)}>
        {Math.round(progress * 100)}%
      </progress>
      <div aria-hidden="true" className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
    </section>
  )
}

function timerStatusLabel(status: WarmupSessionTimerData['status']): string {
  if (status === 'running') return 'Идёт'
  if (status === 'paused') return 'Пауза'
  if (status === 'completed') return 'Завершён'
  return 'Остановлен'
}

function timerStatusTone(status: WarmupSessionTimerData['status']): 'green' | 'amber' | 'gray' {
  if (status === 'running') return 'green'
  if (status === 'paused') return 'amber'
  return 'gray'
}
