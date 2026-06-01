// fallow-ignore-file complexity
// fallow-ignore-reason: Settings page composition root; policy panels remain split below this shell.
import { useQuery } from '@tanstack/react-query'
import { Button, PageHeader, PageShell, SectionCard, StatusCard, StatusPill, Switch } from '@stylisttg/ui'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { AnimatedPage } from '@/components/ui/AnimatedPage'
import {
  auditEventsQueryOptions,
  currentUserQueryOptions,
  frontendDiagnosticsQueryOptions,
  globalOperationLogsQueryOptions,
  settingsBundleQueryOptions,
  workerDiagnosticsQueryOptions,
} from '@/lib/queries'
import { compactOperationLogLabel, type OperationLog } from '@/lib/operationLogs'
import { getLiveStatus } from '@/lib/liveStatus'
import { hasConfiguredRateLimits } from '@/lib/workerDiagnostics'
import { SafetyPolicyPanel } from '@/features/settings/SafetyPolicyPanel'
import type { SettingsBundle } from '@/lib/queryTypes'
import type { FrontendDiagnosticsSummary, WorkerDiagnostics } from '@/lib/api'

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} сек`
  if (seconds === 3600) return '1 час'
  if (seconds % 60 === 0) return `${seconds / 60} минут`
  return `${Math.round(seconds / 60)} минут`
}

type SettingsPageProps = {
  includeSafetyPolicy?: boolean
}

export function SettingsPage({ includeSafetyPolicy = false }: SettingsPageProps) {
  const settingsQuery = useQuery(settingsBundleQueryOptions())
  const currentUserQuery = useQuery(currentUserQueryOptions())
  const auditEventsQuery = useQuery(auditEventsQueryOptions(12))
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const operationLogsQuery = useQuery(globalOperationLogsQueryOptions(50))
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const settings = settingsQuery.data
  const diagnostics = diagnosticsQuery.data
  const policy = settings?.policy
  const liveStatus = getLiveStatus(diagnostics, workerDiagnosticsQuery.data)

  return (
    <AnimatedPage>
      <PageShell className="grid gap-5">
        <PageHeader
          eyebrow="Настройки"
          title="Настройки рабочей области"
          description="Конфигурация рабочей области, безопасности и расширенные параметры."
        />

        <WorkspaceSettingsSection diagnostics={diagnostics} />
        <SecuritySettingsSection />

        {includeSafetyPolicy ? (
          <SafetyPolicyPanel currentUserRole={currentUserQuery.data?.role} />
        ) : null}

        <CooldownPolicySection policy={policy} />
        <LiveModeSection liveStatus={liveStatus} />
        <AdvancedSettingsSection
          advancedOpen={advancedOpen}
          auditEvents={auditEventsQuery.data?.items ?? []}
          auditError={auditEventsQuery.isError}
          auditPending={auditEventsQuery.isPending}
          operationLogs={operationLogsQuery.data?.items ?? []}
          operationLogsError={operationLogsQuery.isError}
          operationLogsPending={operationLogsQuery.isPending}
          onToggle={() => setAdvancedOpen(!advancedOpen)}
          workerDiagnostics={workerDiagnosticsQuery.data}
        />
      </PageShell>
    </AnimatedPage>
  )
}

function WorkspaceSettingsSection({ diagnostics }: { diagnostics: FrontendDiagnosticsSummary | undefined }) {
  return (
    <SectionCard title="Рабочая область">
      <div className="grid gap-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Среда</span>
          <StatusPill tone={diagnostics?.app_env === 'staging' ? 'green' : 'muted'}>
            {diagnostics?.app_env === 'staging' ? 'Staging' : diagnostics?.app_env === 'local' ? 'Локальная среда' : 'Проверка...'}
          </StatusPill>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Режим авторизации</span>
          <StatusPill tone={diagnostics?.auth_mode === 'supabase_jwt' ? 'green' : 'amber'}>
            {diagnostics?.auth_mode === 'supabase_jwt' ? 'Supabase JWT' : diagnostics?.auth_mode ?? 'Проверка...'}
          </StatusPill>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Хранилище</span>
          <StatusPill tone={diagnostics?.storage.backend === 's3' ? 'green' : 'muted'}>
            {diagnostics?.storage.backend ?? 'Проверка...'}
          </StatusPill>
        </div>
      </div>
    </SectionCard>
  )
}

function SecuritySettingsSection() {
  return (
    <SectionCard title="Безопасность">
      <div className="grid gap-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Режим выполнения задач</span>
          <StatusPill tone="amber">Безопасный mock-режим</StatusPill>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Удаление аккаунтов</span>
          <StatusPill tone="green">Заблокировано</StatusPill>
        </div>
        <p className="text-xs text-muted-foreground">
          Полное удаление аккаунтов отключено по умолчанию. Данные сохраняются для аудита.
        </p>
      </div>
    </SectionCard>
  )
}

function CooldownPolicySection({ policy }: { policy: SettingsBundle['policy'] | undefined }) {
  return (
    <SectionCard title="Паузы безопасности" description="Минимальные интервалы между операциями для защиты аккаунтов.">
      {policy ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <StatusCard label="Обновление профиля" value={formatDuration(policy.profile_update_cooldown_seconds)} detail="между задачами" tone="neutral" />
          <StatusCard label="Юзернейм" value={formatDuration(policy.username_cooldown_seconds)} detail="между изменениями" tone="neutral" />
          <StatusCard label="Фото профиля" value={formatDuration(policy.profile_photo_cooldown_seconds)} detail="между задачами" tone="neutral" />
          <StatusCard label="Музыка профиля" value={formatDuration(policy.profile_music_cooldown_seconds)} detail="между задачами" tone="neutral" />
          <StatusCard label="Публикация историй" value={formatDuration(policy.story_post_cooldown_seconds)} detail="между задачами" tone="neutral" />
          <StatusCard label="Удаление историй" value={formatDuration(policy.story_delete_cooldown_seconds)} detail="между задачами" tone="neutral" />
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">Загрузка настроек...</div>
      )}
    </SectionCard>
  )
}

function LiveModeSection({ liveStatus }: { liveStatus: ReturnType<typeof getLiveStatus> }) {
  const liveModeLabel = liveStatus.enabled ? 'Включён' : 'Отключён'

  return (
    <SectionCard title="Live-режим">
      <div className="grid gap-3 text-sm">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium text-foreground">Live-режим Telegram</div>
            <p className="mt-0.5 text-xs text-muted-foreground">Реальное выполнение задач через Telegram.</p>
          </div>
          <Switch checked={liveStatus.enabled} disabled onCheckedChange={() => {}} label={liveModeLabel} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Среда исполнения</span>
          <StatusPill tone={liveStatus.tone}>{liveStatus.label}</StatusPill>
        </div>
        <p className="text-xs text-muted-foreground">
          Зелёный статус означает, что live включён и исполнительная среда реально готова.
        </p>
      </div>
    </SectionCard>
  )
}

function AdvancedSettingsSection({
  advancedOpen,
  auditError,
  auditEvents,
  auditPending,
  onToggle,
  operationLogs,
  operationLogsError,
  operationLogsPending,
  workerDiagnostics,
}: {
  advancedOpen: boolean
  auditError: boolean
  auditEvents: Array<{ id: string; action: string; entity_type: string; account_id?: string | null; created_at: string }>
  auditPending: boolean
  onToggle: () => void
  operationLogs: OperationLog[]
  operationLogsError: boolean
  operationLogsPending: boolean
  workerDiagnostics: WorkerDiagnostics | undefined
}) {
  return (
    <SectionCard
      title="Расширенные"
      actions={
        <Button variant="ghost" onClick={onToggle} type="button">
          <ChevronDown className={`size-4 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
        </Button>
      }
    >
      {advancedOpen ? (
        <div className="grid gap-5">
          <OperationLogsSection logs={operationLogs} isError={operationLogsError} isPending={operationLogsPending} />
          <WorkerDiagnosticsSection workerDiagnostics={workerDiagnostics} />
          <AuditHistorySection events={auditEvents} isError={auditError} isPending={auditPending} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Журнал операций, диагностика воркеров и история аудита.</p>
      )}
    </SectionCard>
  )
}

function OperationLogsSection({ isError, isPending, logs }: { isError: boolean; isPending: boolean; logs: OperationLog[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-bold text-foreground">Журнал операций</h3>
      {isPending ? (
        <div className="text-sm text-muted-foreground">Загрузка журнала...</div>
      ) : isError ? (
        <div className="text-sm text-destructive">Журнал операций недоступен.</div>
      ) : logs.length > 0 ? (
        <div className="max-h-60 space-y-1.5 overflow-auto">
          {logs.slice(0, 20).map((log) => <OperationLogRow key={log.id} log={log} />)}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">Пока нет записей.</div>
      )}
    </div>
  )
}

function OperationLogRow({ log }: { log: OperationLog }) {
  const createdAt = new Date(log.created_at).toLocaleString('ru-RU')
  return (
    <article className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
      <header className="flex items-center justify-between gap-3">
        <span className="font-semibold text-foreground">{compactOperationLogLabel(log)}</span>
        <time className="text-[11px] text-muted-foreground">{createdAt}</time>
      </header>
      <p className="mt-0.5">{log.message}</p>
    </article>
  )
}

function WorkerDiagnosticsSection({ workerDiagnostics }: { workerDiagnostics: WorkerDiagnostics | undefined }) {
  const rateLimitsConfigured = hasConfiguredRateLimits(workerDiagnostics)

  return (
    <div>
      <h3 className="mb-2 text-sm font-bold text-foreground">Диагностика воркеров</h3>
      <div className="grid gap-2 sm:grid-cols-3">
        <StatusCard label="Планировщик" value={workerDiagnostics?.scheduler.enabled ? 'Включён' : 'Отключён'} tone={workerDiagnostics?.scheduler.enabled ? 'warning' : 'ok'} />
        <StatusCard label="Очиститель" value={workerDiagnostics?.reaper.enabled ? 'Включён' : 'Отключён'} tone="ok" />
        <StatusCard label="Лимиты операций" value={rateLimitsConfigured ? 'Настроены' : 'Проверка...'} tone={rateLimitsConfigured ? 'ok' : 'neutral'} />
      </div>
    </div>
  )
}

function AuditHistorySection({
  events,
  isError,
  isPending,
}: {
  events: Array<{ id: string; action: string; entity_type: string; account_id?: string | null; created_at: string }>
  isError: boolean
  isPending: boolean
}) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-bold text-foreground">История аудита</h3>
      <div className="mb-2 flex flex-wrap gap-2">
        <StatusPill tone="green">Только чтение</StatusPill>
        <StatusPill tone="amber">Секреты скрыты</StatusPill>
      </div>
      {isPending ? (
        <div className="text-sm text-muted-foreground">Загрузка событий аудита...</div>
      ) : isError ? (
        <div className="text-sm text-muted-foreground">История аудита недоступна.</div>
      ) : events.length > 0 ? (
        <div className="max-h-48 space-y-1.5 overflow-auto">
          {events.map((event) => (
            <div className="rounded-lg border border-border bg-muted px-3 py-2" key={event.id}>
              <div className="text-sm font-semibold text-foreground">{event.action}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {event.entity_type}
                {event.account_id ? ` · ${event.account_id}` : ''}
                {' · '}
                {new Date(event.created_at).toLocaleString('ru-RU')}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">Нет событий аудита.</div>
      )}
    </div>
  )
}
