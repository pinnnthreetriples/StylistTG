import { Alert, Badge, Button, SectionCard } from '@stylisttg/ui'
import { PauseCircle, PlayCircle, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { SafetyGateBanner } from '@/modules/shared'

import {
  usePauseWarmupSession,
  useResumeWarmupSession,
  useWarmupActionMetadata,
  useWarmupSessionDetail,
  useWarmupStrategies,
} from '../hooks'
import {
  WARMUP_EXECUTION_MODE_LABELS,
  formatWarmupNextStep,
  warmupProgressPercent,
} from '../labels'
import type { WarmupSessionSummary } from '../types'
import { WarmupDailyCountersPanel } from './WarmupDailyCountersPanel'
import { WarmupDisabledActionsToggle } from './WarmupDisabledActionsToggle'
import { WarmupIsolationBanner } from './WarmupIsolationBanner'
import { WarmupLiveLogs } from './WarmupLiveLogs'
import { WarmupProxySnapshotPanel } from './WarmupProxySnapshotPanel'
import { WarmupStatusBadge } from './WarmupStatusBadge'

export function WarmupSessionDetail({
  session,
  workersEnabled,
}: {
  session: WarmupSessionSummary | null
  workersEnabled?: boolean
}) {
  const [pauseReason, setPauseReason] = useState('')
  const detailQuery = useWarmupSessionDetail(session?.id ?? null)
  const actionMetadataQuery = useWarmupActionMetadata()
  const strategiesQuery = useWarmupStrategies()
  const pauseMutation = usePauseWarmupSession()
  const resumeMutation = useResumeWarmupSession()
  const detail = detailQuery.data ?? null
  const strategy =
    strategiesQuery.data?.find((entry) => entry.id === detail?.strategy_id) ?? null

  if (!session) {
    return (
      <SectionCard title="Детали сессии" description="Выберите сессию в таблице.">
        <div className="rounded-lg border border-dashed border-border bg-muted px-4 py-6 text-sm text-muted-foreground">
          Откройте сессию, чтобы увидеть текущий день, состояние воркера, паузу и журнал событий.
        </div>
      </SectionCard>
    )
  }

  const canPause = session.status === 'scheduled' || session.status === 'active'
  const canResume = session.status === 'paused_manual' || session.status === 'paused_risk'
  const progress = warmupProgressPercent(session.current_day, session.duration_days)
  const executionLabel = WARMUP_EXECUTION_MODE_LABELS[session.execution_mode] ?? session.execution_mode
  const isDryRun = session.execution_mode === 'dry_run'
  const executionTone = isDryRun ? 'gray' : 'amber'
  const cycleConfig = detail?.cycle_config ?? session.cycle_config

  return (
    <div className="grid gap-4">
      <SafetyGateBanner accountId={session.account_id} intent="warmup" />
      <WarmupIsolationBanner accountId={session.account_id} />
      <SectionCard title="Открытая сессия" description="Что происходит сейчас и когда система сможет сделать следующий шаг.">
        <div className="grid gap-3">
          <div className="rounded-lg border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
            {isDryRun
              ? `Сейчас аккаунт не выполняет действий в Telegram. Система только проверяет готовность, ведёт ${session.duration_days}-дневный план, блокирует конфликтующие изменения и пишет журнал.`
              : `Активен режим «${executionLabel}»: модуль управляет аккаунтом по плану на ${session.duration_days} дней. Сторонние модули временно не могут с ним взаимодействовать.`}
          </div>
          <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs leading-5 text-muted-foreground">
            {isDryRun
              ? 'Реальные действия в Telegram появятся только после отдельного включения live-воркера и явного списка разрешённых действий. Сейчас модуль ничего не подписывает, не отправляет, не реагирует и не меняет профиль.'
              : 'Подробный список выполняемых действий определяется выбранным режимом. Журнал событий ниже отражает каждый шаг подготовки.'}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">Аккаунт</div>
              <div className="text-sm font-semibold text-foreground">{session.account_label ?? session.account_id}</div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">Стратегия</div>
              <div className="text-sm font-semibold text-foreground">{session.strategy_name}</div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">Статус</div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <WarmupStatusBadge status={session.status} coldSoakUntil={session.cold_soak_until} />
                <Badge tone={executionTone}>
                  <Sparkles className="size-3" />
                  {executionLabel}
                </Badge>
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">
                {session.next_micro_session_at ? 'Следующее окно микро-сессии' : 'Следующий шаг'}
              </div>
              <div className="text-sm font-semibold text-foreground">
                {formatWarmupNextStep(
                  session.next_micro_session_at ?? session.next_step_at,
                  workersEnabled,
                )}
              </div>
            </div>
            {cycleConfig ? (
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">Циклическое окно</div>
                <div className="text-sm font-semibold text-foreground">
                  Ожидаются активные часы: {formatHour(cycleConfig.start_hour)}-{formatHour(cycleConfig.end_hour)}
                </div>
              </div>
            ) : null}
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs font-semibold text-muted-foreground">
              <span>Прогресс</span>
              <span>{session.current_day} / {session.duration_days} дней</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-foreground" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
        <div className="mt-4 grid gap-2 border-t border-border pt-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Причина паузы</span>
            <input
              className="h-9 rounded-md border border-border px-3 text-sm"
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
      <WarmupDailyCountersPanel
        currentDay={detail?.current_day ?? session.current_day}
        durationDays={detail?.duration_days ?? session.duration_days}
        dailyCounters={detail?.daily_counters ?? {}}
        strategy={strategy}
      />
      <WarmupDisabledActionsToggle
        sessionId={session.id}
        disabledActions={detail?.disabled_actions ?? []}
        metadata={actionMetadataQuery.data ?? []}
        isMetadataLoading={actionMetadataQuery.isLoading}
      />
      <WarmupProxySnapshotPanel snapshot={detail?.proxy_snapshot ?? null} />
      <WarmupLiveLogs />
    </div>
  )
}

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}
