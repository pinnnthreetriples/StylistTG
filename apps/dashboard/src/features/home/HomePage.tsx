import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, MetricCard, PageHeader, PageShell, ProductEmptyState, StatusPill } from '@stylisttg/ui'
import { Plus, CheckCircle2, AlertTriangle, ShieldAlert, Activity, ArrowRight, Lock } from 'lucide-react'

import { AnimatedPage } from '@/components/ui/AnimatedPage'
import { AnimatedSection } from '@/components/ui/AnimatedSection'
import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { fetchReady } from '@/lib/api'
import {
  accountsQueryOptions,
  accountRiskSummaryQueryOptions,
  frontendDiagnosticsQueryOptions,
  workerDiagnosticsQueryOptions,
} from '@/lib/queries'
import { getLiveStatus } from '@/lib/liveStatus'
import { labelHealthDependency } from '@/lib/uiLabels'

export function HomePage() {
  const accountsQuery = useQuery(accountsQueryOptions())
  const riskQuery = useQuery(accountRiskSummaryQueryOptions())
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
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
  const liveStatus = getLiveStatus(diagnosticsQuery.data, workerDiagnosticsQuery.data)
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

        <AnimatedSection>
          <Card className="grid gap-5 p-6 lg:grid-cols-[1.4fr_0.6fr] lg:items-center">
            <div>
              <div className="mb-2 inline-flex items-center rounded-full bg-navy-50 px-3 py-1 text-xs font-semibold text-navy-700">
                Что требует внимания
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-navy-950">{heroTitle}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-500">{heroDescription}</p>
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
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div className="text-xs font-semibold uppercase text-gray-500">Live-режим</div>
              <div className="mt-2 text-lg font-bold text-navy-950">{liveStatus.label}</div>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                Зелёный статус означает, что live включён и исполнительная среда реально готова.
              </p>
            </div>
          </Card>
        </AnimatedSection>

        {highRiskCount > 0 ? (
          <Alert variant="warning" icon={<ShieldAlert className="size-5" />}>
            <div className="font-semibold">Высокий риск у {highRiskCount} аккаунтов</div>
            <div className="mt-1 text-sm opacity-80">Перед изменением профиля проверьте причины риска и завершите нужные действия.</div>
          </Alert>
        ) : accounts.length === 0 ? (
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
        ) : null}

        <AnimatedSection>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
            <MetricCard icon={<CheckCircle2 className="size-4" />} label="Всего аккаунтов" value={accountsQuery.isLoading ? '...' : accounts.length} />
            <MetricCard icon={<CheckCircle2 className="size-4" />} label="Готовы к задачам" value={accountsQuery.isLoading ? '...' : readyAccounts} />
            <MetricCard icon={<AlertTriangle className="size-4" />} label="Требуют внимания" value={riskQuery.isLoading ? '...' : attentionCount} />
            <MetricCard icon={<ShieldAlert className="size-4" />} label="Высокий риск" value={riskQuery.isLoading ? '...' : highRiskCount} />
            <MetricCard label="Нужен повторный вход" value={riskQuery.isLoading ? '...' : riskSummary.reauth_required} />
            <MetricCard label="Без прокси" value={riskQuery.isLoading ? '...' : riskSummary.proxy_problem} />
          </div>
        </AnimatedSection>

        <AnimatedSection>
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="p-6">
              <h3 className="text-lg font-medium flex items-center gap-2 mb-4">
                <Activity className="size-5" />
                Текущие действия
              </h3>
              {dataUnavailable ? (
                <p className="text-sm text-amber-700">Данные пока недоступны. Проверьте состояние системы.</p>
              ) : (
                <div className="grid gap-3 text-sm text-gray-500">
                  <p>Активных задач нет. Создайте задачу из карточки аккаунта после проверки риска.</p>
                  <Link className="font-semibold text-navy-700 hover:text-navy-900" to="/accounts">
                    Открыть аккаунты
                  </Link>
                </div>
              )}
            </Card>

            <Card className="p-6">
              <h3 className="text-lg font-medium mb-4">Состояние системы</h3>
              <div className="space-y-3">
                 <div className="flex justify-between items-center text-sm">
                   <span className="text-muted-foreground">API backend</span>
                   <StatusPill tone={readyQuery.isError ? 'red' : readyQuery.data ? 'green' : 'muted'}>
                     {readyQuery.isError ? 'Недоступен' : readyQuery.data ? 'Работает' : 'Проверка...'}
                   </StatusPill>
                 </div>
                 <div className="flex justify-between items-center text-sm">
                   <span className="text-muted-foreground">Очереди (Worker)</span>
                   <StatusPill tone={workerDiagnosticsQuery.data ? 'green' : workerDiagnosticsQuery.isError ? 'red' : 'muted'}>
                     {workerDiagnosticsQuery.data ? 'Настроены' : workerDiagnosticsQuery.isError ? 'Недоступны' : 'Проверка...'}
                   </StatusPill>
                 </div>
                 <div className="flex justify-between items-center text-sm">
                   <span className="text-muted-foreground">База данных</span>
                   <StatusPill tone={readyQuery.data?.database === 'ok' ? 'green' : readyQuery.data ? 'red' : 'muted'}>
                     {labelHealthDependency(readyQuery.data?.database)}
                   </StatusPill>
                 </div>
                 <div className="flex justify-between items-center text-sm">
                   <span className="text-muted-foreground">Live-режим</span>
                   <StatusPill tone={liveStatus.tone}>
                     {liveStatus.label}
                   </StatusPill>
                 </div>
              </div>
            </Card>
          </div>
        </AnimatedSection>

        <AnimatedSection>
          <h3 className="text-lg font-medium mb-4 mt-2">Будущие модули</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-5 opacity-75 bg-muted/30">
              <Lock className="mb-3 size-4 text-gray-400" />
              <div className="font-medium">Кампании и прогрев</div>
              <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
            </Card>
            <Card className="p-5 opacity-70 bg-muted/30">
              <Lock className="mb-3 size-4 text-gray-400" />
              <div className="font-medium">AI-ответы</div>
              <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
            </Card>
            <Card className="p-5 opacity-70 bg-muted/30">
              <Lock className="mb-3 size-4 text-gray-400" />
              <div className="font-medium">Биллинг и аналитика</div>
              <p className="text-xs text-muted-foreground mt-2">Подготовлено в архитектуре. Будет добавлено позже.</p>
            </Card>
          </div>
        </AnimatedSection>

      </PageShell>
    </AnimatedPage>
  )
}
