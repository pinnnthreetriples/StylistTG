// fallow-ignore-file complexity
// fallow-ignore-reason: Home overview composition surface; card-level logic stays in local helpers.
import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, MetricCard, PageHeader, PageShell, ProductEmptyState, StatusPill } from '@stylisttg/ui'
import { Plus, CheckCircle2, AlertTriangle, ShieldAlert, Activity, ArrowRight, Lock } from 'lucide-react'

import { AnimatedPage } from '@/components/ui/AnimatedPage'
import { AnimatedSection } from '@/components/ui/AnimatedSection'
import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { fetchReady, fetchWorkerQueues } from '@/lib/api'
import {
  accountsQueryOptions,
  accountRiskSummaryQueryOptions,
  frontendDiagnosticsQueryOptions,
} from '@/lib/queries'
import { getLiveStatus } from '@/lib/liveStatus'
import { labelHealthDependency } from '@/lib/uiLabels'
import { getHomeApiReadinessStatus } from './readinessStatus'

export function HomePage() {
  const accountsQuery = useQuery(accountsQueryOptions())
  const riskQuery = useQuery(accountRiskSummaryQueryOptions())
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerQueuesQuery = useQuery({
    queryKey: ['home', 'workers', 'queues'],
    queryFn: fetchWorkerQueues,
  })
  const readyQuery = useQuery({
    queryKey: ['home', 'ready'],
    queryFn: fetchReady,
    staleTime: 30_000,
  })

  const accounts = accountsQuery.data ?? []
  const riskSummary = riskQuery.data ?? EMPTY_ACCOUNT_RISK_SUMMARY
  const readyAccounts = accounts.filter((account) => account.is_execution_usable).length
  const attentionCount = riskSummary.medium + riskSummary.high + riskSummary.critical
  const highRiskCount = riskSummary.high + riskSummary.critical
  const dataUnavailable = accountsQuery.isError || riskQuery.isError || readyQuery.isError
  const dbStatus = diagnosticsQuery.data?.db.status
  const apiReadiness = getHomeApiReadinessStatus(readyQuery.data, readyQuery.isError)
  const liveStatus = getLiveStatus(diagnosticsQuery.data)
  const heroTitle =
    accounts.length === 0
      ? 'Добавьте первый аккаунт'
      : attentionCount > 0
        ? `${attentionCount} аккаунт требует внимания`
        : 'Аккаунты готовы к работе'
  const heroDescription =
    accounts.length === 0
      ? 'После добавления вы сможете редактировать профиль, истории, музыку и прокси.'
      : attentionCount > 0
        ? 'Проверьте авторизацию и риск перед запуском задач.'
        : 'Система не показывает критических действий по аккаунтам.'

  return (
    <AnimatedPage>
      <PageShell className="grid gap-6">
        <PageHeader
          eyebrow="Контрольная панель"
          title="Контрольная панель"
          description="Состояние аккаунтов, задач и инфраструктуры рабочей области."
          actions={
            <Link to="/accounts/add">
              <Button type="button" variant="secondary">
                <Plus className="size-4 mr-2" />
                Добавить аккаунты
              </Button>
            </Link>
          }
        />

        <HomeHero heroDescription={heroDescription} heroTitle={heroTitle} liveStatus={liveStatus} />
        <HomeAttention highRiskCount={highRiskCount} hasAccounts={accounts.length > 0} />
        <HomeMetrics
          accountCount={accounts.length}
          accountsLoading={accountsQuery.isLoading}
          attentionCount={attentionCount}
          highRiskCount={highRiskCount}
          readyAccounts={readyAccounts}
          riskLoading={riskQuery.isLoading}
          riskSummary={riskSummary}
        />
        <HomeOperationalStatus
          apiReadiness={apiReadiness}
          dataUnavailable={dataUnavailable}
          dbStatus={dbStatus}
          liveStatus={liveStatus}
          workerAvailable={Boolean(workerQueuesQuery.data)}
          workerError={workerQueuesQuery.isError}
        />
        <FutureModules />

      </PageShell>
    </AnimatedPage>
  )
}

function HomeHero({
  heroDescription,
  heroTitle,
  liveStatus,
}: {
  heroDescription: string
  heroTitle: string
  liveStatus: ReturnType<typeof getLiveStatus>
}) {
  return (
    <AnimatedSection>
      <Card className="grid gap-5 p-6 lg:grid-cols-[1.4fr_0.6fr] lg:items-center">
        <div>
          <div className="mb-2 inline-flex items-center rounded-full bg-muted px-3 py-1 text-xs font-semibold text-foreground">
            Что требует внимания
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">{heroTitle}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{heroDescription}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/accounts">
              <Button type="button" variant="secondary">
                Открыть аккаунты
                <ArrowRight className="size-4" />
              </Button>
            </Link>
            <Link to="/accounts/add">
              <Button type="button" variant="secondary">
                Добавить аккаунты
              </Button>
            </Link>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-muted p-4">
          <div className="text-xs font-semibold uppercase text-muted-foreground">Live-режим</div>
          <div className="mt-2 text-lg font-bold text-foreground">{liveStatus.label}</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Зелёный статус означает, что live включён и исполнительная среда реально готова.
          </p>
        </div>
      </Card>
    </AnimatedSection>
  )
}

function HomeAttention({ hasAccounts, highRiskCount }: { hasAccounts: boolean; highRiskCount: number }) {
  if (highRiskCount > 0) {
    return (
      <Alert variant="warning" icon={<ShieldAlert className="size-5" />}>
        <div className="font-semibold">Высокий риск у {highRiskCount} аккаунтов</div>
        <div className="mt-1 text-sm opacity-80">Перед изменением профиля проверьте причины риска и завершите нужные действия.</div>
      </Alert>
    )
  }
  if (hasAccounts) return null

  return (
    <ProductEmptyState
      title="Добавьте первый Telegram-аккаунт"
      description="После добавления вы сможете редактировать профиль, истории, музыку, прокси и видеть риск блокировки."
      action={
        <Link to="/accounts/add">
          <Button type="button" variant="secondary">Добавить аккаунты</Button>
        </Link>
      }
      secondaryAction={
        <Link to="/health">
          <Button type="button" variant="secondary">Проверить систему</Button>
        </Link>
      }
    />
  )
}

function HomeMetrics({
  accountCount,
  accountsLoading,
  attentionCount,
  highRiskCount,
  readyAccounts,
  riskLoading,
  riskSummary,
}: {
  accountCount: number
  accountsLoading: boolean
  attentionCount: number
  highRiskCount: number
  readyAccounts: number
  riskLoading: boolean
  riskSummary: typeof EMPTY_ACCOUNT_RISK_SUMMARY
}) {
  return (
    <AnimatedSection>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        <MetricCard icon={<CheckCircle2 className="size-4" />} label="Всего аккаунтов" value={accountsLoading ? '...' : accountCount} />
        <MetricCard icon={<CheckCircle2 className="size-4" />} label="Готовы к задачам" value={accountsLoading ? '...' : readyAccounts} />
        <MetricCard icon={<AlertTriangle className="size-4" />} label="Требуют внимания" value={riskLoading ? '...' : attentionCount} />
        <MetricCard icon={<ShieldAlert className="size-4" />} label="Высокий риск" value={riskLoading ? '...' : highRiskCount} />
        <MetricCard label="Нужен повторный вход" value={riskLoading ? '...' : riskSummary.reauth_required} />
        <MetricCard label="Без прокси" value={riskLoading ? '...' : riskSummary.proxy_problem} />
      </div>
    </AnimatedSection>
  )
}

function HomeOperationalStatus({
  apiReadiness,
  dataUnavailable,
  dbStatus,
  liveStatus,
  workerAvailable,
  workerError,
}: {
  apiReadiness: ReturnType<typeof getHomeApiReadinessStatus>
  dataUnavailable: boolean
  dbStatus: string | undefined
  liveStatus: ReturnType<typeof getLiveStatus>
  workerAvailable: boolean
  workerError: boolean
}) {
  return (
    <AnimatedSection>
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h3 className="text-lg font-medium flex items-center gap-2 mb-4">
            <Activity className="size-5" />
            Текущие действия
          </h3>
          {dataUnavailable ? (
            <p className="text-sm text-muted-foreground">Данные пока недоступны. Проверьте состояние системы.</p>
          ) : (
            <div className="grid gap-3 text-sm text-muted-foreground">
              <p>Активных задач нет. Создайте задачу из карточки аккаунта после проверки риска.</p>
              <Link className="font-semibold text-foreground hover:text-foreground" to="/accounts">
                Открыть аккаунты
              </Link>
            </div>
          )}
        </Card>
        <HomeSystemStatus apiReadiness={apiReadiness} dbStatus={dbStatus} liveStatus={liveStatus} workerAvailable={workerAvailable} workerError={workerError} />
      </div>
    </AnimatedSection>
  )
}

function HomeSystemStatus({
  apiReadiness,
  dbStatus,
  liveStatus,
  workerAvailable,
  workerError,
}: {
  apiReadiness: ReturnType<typeof getHomeApiReadinessStatus>
  dbStatus: string | undefined
  liveStatus: ReturnType<typeof getLiveStatus>
  workerAvailable: boolean
  workerError: boolean
}) {
  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium mb-4">Состояние системы</h3>
      <div className="space-y-3">
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">API backend</span>
          <StatusPill tone={apiReadiness.tone}>{apiReadiness.label}</StatusPill>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Очереди (Worker)</span>
          <StatusPill tone={workerAvailable ? 'green' : workerError ? 'red' : 'muted'}>
            {workerAvailable ? 'Настроены' : workerError ? 'Недоступны' : 'Проверка...'}
          </StatusPill>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">База данных</span>
          <StatusPill tone={dbStatus === 'ok' ? 'green' : dbStatus ? 'red' : 'muted'}>
            {labelHealthDependency(dbStatus)}
          </StatusPill>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Live-режим</span>
          <StatusPill tone={liveStatus.tone}>{liveStatus.label}</StatusPill>
        </div>
      </div>
    </Card>
  )
}

function FutureModules() {
  return (
    <AnimatedSection>
      <h3 className="text-lg font-medium mb-4 mt-2">Будущие модули</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 opacity-75 bg-muted/30">
          <Lock className="mb-3 size-4 text-muted-foreground" />
          <div className="font-medium">Кампании и прогрев</div>
          <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
        </Card>
        <Card className="p-5 opacity-70 bg-muted/30">
          <Lock className="mb-3 size-4 text-muted-foreground" />
          <div className="font-medium">AI-ответы</div>
          <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
        </Card>
        <Card className="p-5 opacity-70 bg-muted/30">
          <Lock className="mb-3 size-4 text-muted-foreground" />
          <div className="font-medium">Биллинг и аналитика</div>
          <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
        </Card>
      </div>
    </AnimatedSection>
  )
}
