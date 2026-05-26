import { Badge, Button, SectionCard } from '@stylisttg/ui'
import { CalendarClock, Eye, Sparkles, Trash2, UserRound } from 'lucide-react'

import { useDeleteWarmupSession } from '../hooks'
import {
  WARMUP_EXECUTION_MODE_LABELS,
  formatWarmupNextStep,
  warmupProgressPercent,
} from '../labels'
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
  return (
    <SectionCard title="Сессии подготовки" description="Статус, прогресс и ближайший шаг по каждому аккаунту.">
      <div className="grid gap-3">
        {sessions.map((session) => (
          <WarmupSessionCard
            key={session.id}
            session={session}
            workersEnabled={workersEnabled}
            onSelect={onSelect}
            onDeleted={onDeleted}
          />
        ))}
      </div>
    </SectionCard>
  )
}

function WarmupSessionCard({
  session,
  workersEnabled,
  onSelect,
  onDeleted,
}: {
  session: WarmupSessionSummary
  workersEnabled?: boolean
  onSelect: (sessionId: string) => void
  onDeleted?: (sessionId: string) => void
}) {
  const deleteMutation = useDeleteWarmupSession()
  const progress = warmupProgressPercent(session.current_day, session.duration_days)
  const executionLabel = WARMUP_EXECUTION_MODE_LABELS[session.execution_mode] ?? session.execution_mode
  const executionTone = session.execution_mode === 'dry_run' ? 'gray' : 'amber'

  return (
    <article className="rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_140px] lg:items-center">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <UserRound className="size-4 shrink-0 text-muted-foreground" />
            <h3 className="truncate text-sm font-semibold text-foreground">
              {session.account_label ?? session.account_id}
            </h3>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">{session.strategy_name}</span>
            <Badge tone={executionTone}>
              <Sparkles className="size-3" />
              {executionLabel}
            </Badge>
          </div>
        </div>
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <WarmupStatusBadge status={session.status} />
            <span className="text-xs font-semibold text-muted-foreground">
              День {session.current_day} из {session.duration_days}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-foreground" style={{ width: `${progress}%` }} />
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CalendarClock className="size-3.5" />
            {session.next_micro_session_at
              ? `Окно микро-сессии: ${formatWarmupNextStep(session.next_micro_session_at, workersEnabled)}`
              : `Следующий шаг: ${formatWarmupNextStep(session.next_step_at, workersEnabled)}`}
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
}
