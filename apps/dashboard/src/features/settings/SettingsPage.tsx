import { useQuery } from '@tanstack/react-query'
import { Button, PageHeader, PageShell, SectionCard, StatusCard, StatusPill, Switch } from '@stylisttg/ui'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { AnimatedPage } from '@/components/ui/AnimatedPage'
import {
  auditEventsQueryOptions,
  frontendDiagnosticsQueryOptions,
  globalOperationLogsQueryOptions,
  settingsBundleQueryOptions,
  workerDiagnosticsQueryOptions,
} from '@/lib/queries'
import { compactOperationLogLabel, type OperationLog } from '@/lib/operationLogs'
import { getLiveStatus } from '@/lib/liveStatus'

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} сек`
  if (seconds === 3600) return '1 час'
  if (seconds % 60 === 0) return `${seconds / 60} минут`
  return `${Math.round(seconds / 60)} минут`
}

export function SettingsPage() {
  const settingsQuery = useQuery(settingsBundleQueryOptions())
  const auditEventsQuery = useQuery(auditEventsQueryOptions(12))
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const operationLogsQuery = useQuery(globalOperationLogsQueryOptions(50))
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const diagnostics = diagnosticsQuery.data
  const settings = settingsQuery.data
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

        {/* Рабочая область */}
        <SectionCard title="Рабочая область">
          <div className="grid gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Среда</span>
              <StatusPill tone={diagnostics?.app_env === 'staging' ? 'green' : 'muted'}>
                {diagnostics?.app_env === 'staging' ? 'Staging' : diagnostics?.app_env === 'local' ? 'Локальная среда' : 'Проверка...'}
              </StatusPill>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Режим авторизации</span>
              <StatusPill tone={diagnostics?.auth_mode === 'supabase_jwt' ? 'green' : 'amber'}>
                {diagnostics?.auth_mode === 'supabase_jwt' ? 'Supabase JWT' : diagnostics?.auth_mode ?? 'Проверка...'}
              </StatusPill>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Хранилище</span>
              <StatusPill tone={diagnostics?.storage.backend === 's3' ? 'green' : 'muted'}>
                {diagnostics?.storage.backend ?? 'Проверка...'}
              </StatusPill>
            </div>
          </div>
        </SectionCard>

        {/* Безопасность */}
        <SectionCard title="Безопасность">
          <div className="grid gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Режим выполнения задач</span>
              <StatusPill tone="amber">Безопасный mock-режим</StatusPill>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Удаление аккаунтов</span>
              <StatusPill tone="green">Заблокировано</StatusPill>
            </div>
            <p className="text-xs text-gray-400">
              Полное удаление аккаунтов отключено по умолчанию. Данные сохраняются для аудита.
            </p>
          </div>
        </SectionCard>

        {/* Паузы безопасности */}
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
            <div className="text-sm text-gray-500">Загрузка настроек...</div>
          )}
        </SectionCard>

        {/* Live-режим */}
        <SectionCard title="Live-режим">
          <div className="grid gap-3 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-700">Live-режим Telegram</div>
                <p className="mt-0.5 text-xs text-gray-400">Реальное выполнение задач через Telegram.</p>
              </div>
              <Switch checked={false} disabled onCheckedChange={() => {}} label="Отключён" />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Среда исполнения</span>
              <StatusPill tone={liveStatus.tone}>{liveStatus.label}</StatusPill>
            </div>
            <p className="text-xs text-gray-400">
              Зелёный статус означает, что live включён и исполнительная среда реально готова.
            </p>
          </div>
        </SectionCard>

        {/* Расширенные */}
        <SectionCard
          title="Расширенные"
          actions={
            <Button variant="ghost" onClick={() => setAdvancedOpen(!advancedOpen)} type="button">
              <ChevronDown className={`size-4 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
            </Button>
          }
        >
          {advancedOpen ? (
            <div className="grid gap-5">
              {/* Журнал операций */}
              <div>
                <h3 className="mb-2 text-sm font-bold text-gray-900">Журнал операций</h3>
                {operationLogsQuery.isPending ? (
                  <div className="text-sm text-gray-500">Загрузка журнала...</div>
                ) : operationLogsQuery.isError ? (
                  <div className="text-sm text-red-500">Журнал операций недоступен.</div>
                ) : operationLogsQuery.data.items.length > 0 ? (
                  <div className="max-h-60 space-y-1.5 overflow-auto">
                    {operationLogsQuery.data.items.slice(0, 20).map((log: OperationLog) => (
                      <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" key={log.id}>
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-semibold text-gray-800">{compactOperationLogLabel(log)}</span>
                          <span className="text-[11px] text-gray-400">{new Date(log.created_at).toLocaleString('ru-RU')}</span>
                        </div>
                        <p className="mt-0.5 text-gray-500">{log.message}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">Пока нет записей.</div>
                )}
              </div>

              {/* Worker diagnostics */}
              <div>
                <h3 className="mb-2 text-sm font-bold text-gray-900">Диагностика воркеров</h3>
                <div className="grid gap-2 sm:grid-cols-3">
                  <StatusCard
                    label="Планировщик"
                    value={workerDiagnosticsQuery.data?.scheduler.enabled ? 'Включён' : 'Отключён'}
                    tone={workerDiagnosticsQuery.data?.scheduler.enabled ? 'warning' : 'ok'}
                  />
                  <StatusCard
                    label="Очиститель"
                    value={workerDiagnosticsQuery.data?.reaper.enabled ? 'Включён' : 'Отключён'}
                    tone="ok"
                  />
                  <StatusCard
                    label="Лимиты операций"
                    value={workerDiagnosticsQuery.data?.rate_limits.enabled ? 'Настроены' : 'Проверка...'}
                    tone={workerDiagnosticsQuery.data?.rate_limits.enabled ? 'ok' : 'neutral'}
                  />
                </div>
              </div>

              {/* Audit history */}
              <div>
                <h3 className="mb-2 text-sm font-bold text-gray-900">История аудита</h3>
                <div className="mb-2 flex flex-wrap gap-2">
                  <StatusPill tone="green">Только чтение</StatusPill>
                  <StatusPill tone="amber">Секреты скрыты</StatusPill>
                </div>
                {auditEventsQuery.isPending ? (
                  <div className="text-sm text-gray-500">Загрузка событий аудита...</div>
                ) : auditEventsQuery.isError ? (
                  <div className="text-sm text-amber-600">История аудита недоступна.</div>
                ) : auditEventsQuery.data.items.length > 0 ? (
                  <div className="max-h-48 space-y-1.5 overflow-auto">
                    {auditEventsQuery.data.items.map((event) => (
                      <div className="rounded-lg border border-gray-200/70 bg-gray-50 px-3 py-2" key={event.id}>
                        <div className="text-sm font-semibold text-navy-900">{event.action}</div>
                        <div className="mt-1 text-xs text-gray-500">
                          {event.entity_type}
                          {event.account_id ? ` · ${event.account_id}` : ''}
                          {' · '}
                          {new Date(event.created_at).toLocaleString('ru-RU')}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">Нет событий аудита.</div>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Журнал операций, диагностика воркеров и история аудита.</p>
          )}
        </SectionCard>
      </PageShell>
    </AnimatedPage>
  )
}
