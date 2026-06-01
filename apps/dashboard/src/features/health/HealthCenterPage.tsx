// fallow-ignore-file complexity
// fallow-ignore-reason: Health dashboard composition surface; checks stay declarative for scanability.
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, MetricCard, PageHeader, PageShell, SectionCard, StatusCard, StatusPill } from '@stylisttg/ui'
import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { useState } from 'react'

import { AnimatedPage } from '@/components/ui/AnimatedPage'
import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { fetchHealth, fetchReady } from '@/lib/api'
import type { FrontendDiagnosticsSummary, WorkerDiagnostics } from '@/lib/api'
import {
  accountRiskSummaryQueryOptions,
  frontendDiagnosticsQueryOptions,
  jobPoliciesQueryOptions,
  workerDiagnosticsQueryOptions,
} from '@/lib/queries'
import { getLiveStatus, liveStatusCardTone } from '@/lib/liveStatus'
import { labelHealthDependency, labelSystemReadiness } from '@/lib/uiLabels'

export function HealthCenterPage() {
  const healthQuery = useQuery({
    queryKey: ['saas-health-center', 'health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })
  const readyQuery = useQuery({
    queryKey: ['saas-health-center', 'ready'],
    queryFn: fetchReady,
    staleTime: 30_000,
  })
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const jobPoliciesQuery = useQuery(jobPoliciesQueryOptions())
  const accountRiskQuery = useQuery(accountRiskSummaryQueryOptions())
  const ready = readyQuery.data
  const diagnostics = diagnosticsQuery.data
  const workerDiagnostics = workerDiagnosticsQuery.data
  const riskSummary = accountRiskQuery.data ?? EMPTY_ACCOUNT_RISK_SUMMARY
  const liveStatus = getLiveStatus(diagnostics, workerDiagnostics)
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const apiOk = healthQuery.data?.status === 'ok'
  const readyOk = ready?.status === 'ok'
  const dbStatus = diagnostics?.db.status
  const redisStatus = diagnostics?.redis.status
  const dbOk = dbStatus ? dbStatus === 'ok' : readyOk
  const redisOk = redisStatus ? redisStatus === 'ok' : readyOk
  const systemLabel = healthQuery.isError
    ? 'API недоступен'
    : labelSystemReadiness({ apiOk, dbOk: dbOk ?? false, redisOk: redisOk ?? false })

  function refresh() {
    void healthQuery.refetch()
    void readyQuery.refetch()
    void diagnosticsQuery.refetch()
    void workerDiagnosticsQuery.refetch()
    void jobPoliciesQuery.refetch()
    void accountRiskQuery.refetch()
  }

  const SystemIcon = apiOk && dbOk && redisOk ? CheckCircle2 : healthQuery.isError ? XCircle : AlertTriangle
  const systemTone = apiOk && dbOk && redisOk ? 'success' : healthQuery.isError ? 'error' : 'warning'

  return (
    <AnimatedPage>
      <PageShell className="grid gap-5">
        <PageHeader
          eyebrow="Здоровье"
          title="Состояние системы"
          description="Диагностика готовности API, зависимостей, рисков аккаунтов и инфраструктуры."
          actions={
            <Button onClick={refresh} type="button" variant="secondary">
              <RefreshCw className="size-4" />
              Обновить
            </Button>
          }
        />

        <HealthSummaryAlert
          diagnosticsAvailable={Boolean(diagnostics || workerDiagnostics)}
          liveLabel={liveStatus.label}
          systemLabel={systemLabel}
          systemTone={systemTone}
          SystemIcon={SystemIcon}
        />
        <ServiceHealthSection
          apiOk={apiOk}
          dbOk={Boolean(dbOk)}
          dbStatus={dbStatus}
          healthError={healthQuery.isError}
          redisOk={Boolean(redisOk)}
          redisStatus={redisStatus}
        />
        <AccountReadinessSection riskSummary={riskSummary} />
        <QueueHealthSection jobPolicyCount={jobPoliciesQuery.data ? Object.keys(jobPoliciesQuery.data).length : null} workerDiagnostics={workerDiagnostics} />
        <StorageHealthSection diagnostics={diagnostics} />
        <AdvancedDiagnosticsSection
          advancedOpen={advancedOpen}
          diagnostics={diagnostics}
          liveStatus={liveStatus}
          onToggle={() => setAdvancedOpen(!advancedOpen)}
          workerDiagnostics={workerDiagnostics}
        />

        {/* Error states */}
        {readyQuery.isError ? (
          <Alert variant="error">Диагностика готовности недоступна. Проверьте доступность API.</Alert>
        ) : null}
        {diagnosticsQuery.isError ? (
          <Alert variant="warning">Расширенная диагностика бэкенда недоступна.</Alert>
        ) : null}
      </PageShell>
    </AnimatedPage>
  )
}

function HealthSummaryAlert({
  diagnosticsAvailable,
  liveLabel,
  systemLabel,
  systemTone,
  SystemIcon,
}: {
  diagnosticsAvailable: boolean
  liveLabel: string
  systemLabel: string
  systemTone: 'success' | 'error' | 'warning'
  SystemIcon: typeof CheckCircle2
}) {
  return (
    <Alert variant={systemTone} icon={<SystemIcon className="size-5" />}>
      <div className="font-semibold">{systemLabel}</div>
      {diagnosticsAvailable ? <div className="mt-1 text-xs opacity-75">{liveLabel}</div> : null}
    </Alert>
  )
}

function ServiceHealthSection({
  apiOk,
  dbOk,
  dbStatus,
  healthError,
  redisOk,
  redisStatus,
}: {
  apiOk: boolean
  dbOk: boolean
  dbStatus: string | undefined
  healthError: boolean
  redisOk: boolean
  redisStatus: string | undefined
}) {
  return (
    <SectionCard title="Состояние сервиса">
      <div className="grid gap-3 md:grid-cols-3">
        <StatusCard label="API" value={apiOk ? 'Работает' : healthError ? 'Недоступен' : 'Проверка...'} tone={apiOk ? 'ok' : healthError ? 'danger' : 'neutral'} />
        <StatusCard label="База данных" value={labelHealthDependency(dbStatus)} tone={dbOk ? 'ok' : dbStatus ? 'danger' : 'neutral'} />
        <StatusCard label="Redis" value={labelHealthDependency(redisStatus)} tone={redisOk ? 'ok' : redisStatus ? 'danger' : 'neutral'} />
      </div>
    </SectionCard>
  )
}

function AccountReadinessSection({ riskSummary }: { riskSummary: typeof EMPTY_ACCOUNT_RISK_SUMMARY }) {
  return (
    <SectionCard title="Готовность аккаунтов">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Всего аккаунтов" value={riskSummary.total} />
        <MetricCard label="Низкий риск" value={riskSummary.low} />
        <MetricCard label="Средний/высокий" value={riskSummary.medium + riskSummary.high} />
        <MetricCard label="Критический" value={riskSummary.critical} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <StatusPill tone={riskSummary.reauth_required > 0 ? 'red' : 'green'}>
          Нужна авторизация: {riskSummary.reauth_required}
        </StatusPill>
        <StatusPill tone={riskSummary.missing_session + riskSummary.runtime_unhealthy > 0 ? 'amber' : 'green'}>
          Проблемы среды: {riskSummary.missing_session + riskSummary.runtime_unhealthy}
        </StatusPill>
        <StatusPill tone={riskSummary.proxy_problem > 0 ? 'amber' : 'green'}>
          Проблемы прокси: {riskSummary.proxy_problem}
        </StatusPill>
      </div>
    </SectionCard>
  )
}

function QueueHealthSection({
  jobPolicyCount,
  workerDiagnostics,
}: {
  jobPolicyCount: number | null
  workerDiagnostics: WorkerDiagnostics | undefined
}) {
  return (
    <SectionCard title="Очереди и задачи">
      <div className="grid gap-3 md:grid-cols-3">
        <StatusCard
          label="Очереди"
          value={workerDiagnostics ? workerDiagnostics.queues.length : 'Проверка...'}
          tone="info"
          detail={workerDiagnostics ? workerDiagnostics.queues.map((q) => q.name).join(', ') : undefined}
        />
        <StatusCard
          label="Лимиты операций"
          value={workerDiagnostics?.rate_limits.enabled ? 'Настроены' : 'Проверка...'}
          tone={workerDiagnostics?.rate_limits.enabled ? 'ok' : 'neutral'}
        />
        <StatusCard label="Политики повторов" value={jobPolicyCount ?? 'Проверка...'} tone="info" />
      </div>
    </SectionCard>
  )
}

function StorageHealthSection({ diagnostics }: { diagnostics: FrontendDiagnosticsSummary | undefined }) {
  return (
    <SectionCard title="Хранилище">
      <div className="grid gap-3 md:grid-cols-3">
        <StatusCard label="Бэкенд хранилища" value={diagnostics?.storage.backend ?? 'Проверка...'} tone={diagnostics?.storage.backend === 's3' ? 'info' : 'neutral'} />
        <StatusCard label="Ссылки доступа" value={diagnostics?.storage.signed_url_enabled ? 'Включены' : 'Отключены'} tone={diagnostics?.storage.signed_url_enabled ? 'ok' : 'neutral'} />
        <StatusCard label="Хранилище" value={diagnostics?.storage.bucket_configured ? 'Настроен' : 'Не настроен'} tone={diagnostics?.storage.bucket_configured ? 'ok' : 'neutral'} />
      </div>
    </SectionCard>
  )
}

function AdvancedDiagnosticsSection({
  advancedOpen,
  diagnostics,
  liveStatus,
  onToggle,
  workerDiagnostics,
}: {
  advancedOpen: boolean
  diagnostics: FrontendDiagnosticsSummary | undefined
  liveStatus: ReturnType<typeof getLiveStatus>
  onToggle: () => void
  workerDiagnostics: WorkerDiagnostics | undefined
}) {
  return (
    <SectionCard
      title="Расширенная диагностика"
      actions={
        <Button variant="ghost" onClick={onToggle} type="button">
          {advancedOpen ? 'Свернуть' : 'Развернуть'}
        </Button>
      }
    >
      {advancedOpen ? (
        <div className="grid gap-3 md:grid-cols-3">
          <StatusCard label="Live-режим" value={liveStatus.label} tone={liveStatusCardTone(liveStatus)} />
          <StatusCard
            label="Библиотека TDLib"
            value={diagnostics?.tdlib.library_loadable ? 'Загружается' : diagnostics?.tdlib.library_configured ? 'Настроена' : 'Не настроена'}
            tone={diagnostics?.tdlib.library_loadable ? 'ok' : diagnostics?.tdlib.library_configured ? 'warning' : 'neutral'}
          />
          <StatusCard label="Воркер авторизации" value={diagnostics?.tdlib.auth_worker_ready ? 'Готов' : 'Проверка...'} tone={diagnostics?.tdlib.auth_worker_ready ? 'ok' : 'neutral'} />
          <StatusCard
            label="Исполнительная среда"
            value={diagnostics?.tdlib.execution_plane_ready ? 'Готова' : 'Не готова'}
            tone={diagnostics?.tdlib.execution_plane_ready ? 'ok' : liveStatus.enabled ? 'danger' : 'neutral'}
          />
          <StatusCard label="Планировщик" value={workerDiagnostics?.scheduler.enabled ? 'Включён' : 'Отключён'} tone={workerDiagnostics?.scheduler.enabled ? 'warning' : 'ok'} />
          <StatusCard label="Очиститель" value={workerDiagnostics?.reaper.enabled ? String(workerDiagnostics.reaper.mode) : 'Отключён'} tone={workerDiagnostics?.reaper.mode === 'execute_safe' ? 'warning' : 'ok'} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">TDLib, планировщик, очиститель и другие технические детали.</p>
      )}
    </SectionCard>
  )
}
