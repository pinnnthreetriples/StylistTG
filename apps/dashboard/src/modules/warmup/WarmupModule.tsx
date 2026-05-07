import { MetricCard, PageHeader, ProductEmptyState } from '@stylisttg/ui'
import { AlertCircle, CheckCircle2, Clock3 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useWarmupReadiness, useWarmupSessions } from './hooks'
import { WarmupCreateWizard } from './components/WarmupCreateWizard'
import { WarmupReadinessBanner } from './components/WarmupReadinessBanner'
import { WarmupSessionDetail } from './components/WarmupSessionDetail'
import { WarmupSessionsTable } from './components/WarmupSessionsTable'
import type { WarmupSessionSummary } from './types'

const EMPTY_SESSIONS: WarmupSessionSummary[] = []

export function WarmupModule() {
  const readinessQuery = useWarmupReadiness()
  const sessionsQuery = useWarmupSessions()
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const sessions = sessionsQuery.data?.items ?? EMPTY_SESSIONS
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )

  const activeCount = sessions.filter((session) =>
    ['validating', 'scheduled', 'active', 'paused_risk', 'paused_manual'].includes(session.status),
  ).length
  const completedCount = sessions.filter((session) => session.status === 'completed').length
  const failedCount = sessions.filter((session) => session.status === 'failed').length

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Модули"
        title="Прогрев аккаунтов"
        description="Операционный контроль подготовки: проверка готовности, 14-дневное расписание, ручная пауза и аудит без live-действий в Telegram."
      />
      <WarmupReadinessBanner readiness={readinessQuery.data} />
      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard
          icon={<Clock3 className="size-4" />}
          label="В расписании"
          value={activeCount}
          change="Сессии, которые ждут или проходят dry-run шаги"
        />
        <MetricCard
          icon={<CheckCircle2 className="size-4" />}
          label="Завершённые"
          value={completedCount}
          change="Прошли 14 дней подготовки"
        />
        <MetricCard
          icon={<AlertCircle className="size-4" />}
          label="Требуют внимания"
          value={failedCount}
          change="Ошибки очереди или circuit breaker"
        />
      </div>
      <WarmupCreateWizard />
      {sessions.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <WarmupSessionsTable
            sessions={sessions}
            workersEnabled={readinessQuery.data?.workers_enabled}
            onSelect={setSelectedSessionId}
            onDeleted={(sessionId) => {
              if (selectedSessionId === sessionId) setSelectedSessionId(null)
            }}
          />
          <WarmupSessionDetail session={selectedSession} workersEnabled={readinessQuery.data?.workers_enabled} />
        </div>
      ) : (
        <ProductEmptyState
          title="Сессий подготовки пока нет"
          description="Создайте первую сессию после проверки готовности аккаунта."
        />
      )}
    </div>
  )
}
