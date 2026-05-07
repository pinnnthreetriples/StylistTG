import { Alert, Button, SectionCard } from '@stylisttg/ui'
import { PauseCircle, PlayCircle } from 'lucide-react'
import { useState } from 'react'

import { usePauseWarmupSession, useResumeWarmupSession, useWarmupEvents } from '../hooks'
import { formatWarmupNextStep, warmupProgressPercent } from '../labels'
import type { WarmupSessionSummary } from '../types'
import { WarmupEventLog } from './WarmupEventLog'
import { WarmupStatusBadge } from './WarmupStatusBadge'

export function WarmupSessionDetail({
  session,
  workersEnabled,
}: {
  session: WarmupSessionSummary | null
  workersEnabled?: boolean
}) {
  const [pauseReason, setPauseReason] = useState('')
  const eventsQuery = useWarmupEvents(session?.id ?? null)
  const pauseMutation = usePauseWarmupSession()
  const resumeMutation = useResumeWarmupSession()

  if (!session) {
    return (
      <SectionCard title="Детали сессии" description="Выберите сессию в таблице.">
        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
          Откройте сессию, чтобы увидеть текущий день, состояние воркера, паузу и журнал событий.
        </div>
      </SectionCard>
    )
  }

  const canPause = session.status === 'scheduled' || session.status === 'active'
  const canResume = session.status === 'paused_manual' || session.status === 'paused_risk'
  const progress = warmupProgressPercent(session.current_day)

  return (
    <div className="grid gap-4">
      <SectionCard title="Открытая сессия" description="Что происходит сейчас и когда система сможет сделать следующий шаг.">
        <div className="grid gap-3">
          <div className="rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-sm text-sky-800">
            Сейчас аккаунт не выполняет действий в Telegram. Система только проверяет готовность, ведёт 14-дневный план,
            блокирует конфликтующие изменения и пишет журнал.
          </div>
          <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs leading-5 text-gray-600">
            Реальные действия в Telegram появятся только после отдельного включения live-воркера и явного списка разрешённых
            действий. Сейчас модуль ничего не подписывает, не отправляет, не реагирует и не меняет профиль.
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-xs font-semibold uppercase text-gray-400">Аккаунт</div>
              <div className="text-sm font-semibold text-navy-900">{session.account_label ?? session.account_id}</div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-gray-400">Стратегия</div>
              <div className="text-sm font-semibold text-navy-900">{session.strategy_name}</div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-gray-400">Статус</div>
              <div className="mt-1">
                <WarmupStatusBadge status={session.status} />
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-gray-400">Следующий шаг</div>
              <div className="text-sm font-semibold text-navy-900">
                {formatWarmupNextStep(session.next_step_at, workersEnabled)}
              </div>
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs font-semibold text-gray-500">
              <span>Прогресс</span>
              <span>{session.current_day} / 14 дней</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
              <div className="h-full rounded-full bg-gray-950" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
        <div className="mt-4 grid gap-2 border-t border-gray-100 pt-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold uppercase text-gray-500">Причина паузы</span>
            <input
              className="h-9 rounded-md border border-gray-200 px-3 text-sm"
              value={pauseReason}
              aria-label="Причина паузы"
              placeholder="Например: проверка аккаунта, proxy или профиля"
              onChange={(event) => setPauseReason(event.target.value)}
            />
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            disabled={!canPause || pauseMutation.isPending}
            type="button"
            variant="destructive"
            onClick={() => pauseMutation.mutate({ sessionId: session.id, reason: pauseReason || 'Ручная пауза' })}
          >
            <PauseCircle className="size-4" />
            Пауза
          </Button>
          <Button
            disabled={!canResume || resumeMutation.isPending}
            type="button"
            variant="outline"
            onClick={() => resumeMutation.mutate({ sessionId: session.id })}
          >
            <PlayCircle className="size-4" />
            Возобновить
          </Button>
          </div>
        </div>
        {pauseMutation.error || resumeMutation.error ? (
          <Alert className="mt-3" variant="error">
            Не удалось изменить состояние сессии.
          </Alert>
        ) : null}
      </SectionCard>
      <WarmupEventLog events={eventsQuery.data?.items ?? []} />
    </div>
  )
}
