import { Button, SectionCard } from '@stylisttg/ui'
import { CalendarClock, Eye, Trash2, UserRound } from 'lucide-react'

import { useDeleteWarmupSession } from '../hooks'
import { formatWarmupNextStep, warmupProgressPercent } from '../labels'
import type { WarmupSessionSummary } from '../types'
import { WarmupStatusBadge } from './WarmupStatusBadge'

export function WarmupSessionsTable({
  sessions,
  workersEnabled,
  onSelect,
  onDeleted,
}: {
  sessions: WarmupSessionSummary[]
  workersEnabled?: boolean
  onSelect: (sessionId: string) => void
  onDeleted?: (sessionId: string) => void
}) {
  const deleteMutation = useDeleteWarmupSession()

  return (
    <SectionCard title="Сессии подготовки" description="Статус, прогресс и ближайший шаг по каждому аккаунту.">
      <div className="grid gap-3">
        {sessions.map((session) => {
          const progress = warmupProgressPercent(session.current_day)
          return (
            <article className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm" key={session.id}>
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_140px] lg:items-center">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <UserRound className="size-4 shrink-0 text-gray-400" />
                    <h3 className="truncate text-sm font-semibold text-navy-900">
                      {session.account_label ?? session.account_id}
                    </h3>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">{session.strategy_name}</p>
                </div>
                <div className="grid gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <WarmupStatusBadge status={session.status} />
                    <span className="text-xs font-semibold text-gray-500">День {session.current_day} из 14</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                    <div className="h-full rounded-full bg-gray-950" style={{ width: `${progress}%` }} />
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <CalendarClock className="size-3.5" />
                    Следующий шаг: {formatWarmupNextStep(session.next_step_at, workersEnabled)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    className="min-w-0 flex-1"
                    type="button"
                    variant="outline"
                    onClick={() => onSelect(session.id)}
                  >
                    <Eye className="size-4" />
                    Открыть
                  </Button>
                  <Button
                    aria-label={`Удалить сессию подготовки ${session.account_label ?? session.account_id}`}
                    disabled={deleteMutation.isPending}
                    size="icon"
                    type="button"
                    variant="destructive"
                    onClick={() => {
                      const confirmed = window.confirm('Удалить сессию подготовки? История событий этой сессии тоже будет удалена.')
                      if (!confirmed) return
                      deleteMutation.mutate(
                        { sessionId: session.id },
                        { onSuccess: () => onDeleted?.(session.id) },
                      )
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </SectionCard>
  )
}
