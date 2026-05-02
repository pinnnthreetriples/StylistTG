import { CircleHelp, RefreshCw, Server, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import type React from 'react'

import {
  useSettingsBundleQuery,
  useUpdateAuthRuntimeModeMutation,
  useUpdateExecutionPolicyMutation,
} from '@/hooks/queries/useSettingsQueries'
import type { ExecutionPolicyUpdate } from '@/lib/api'
import type { FreshValidityPolicy, RecentFailurePolicy, UnknownCapabilityPolicy } from '@/lib/accountSafety'
import { buildDiagnosticItems } from '@/lib/diagnostics'
import { buildPreflightItems, formatCooldown, type SettingsStatusItem } from '@/lib/settings'

export function SettingsPanel() {
  const settingsQuery = useSettingsBundleQuery()
  const updatePolicyMutation = useUpdateExecutionPolicyMutation()
  const updateAuthModeMutation = useUpdateAuthRuntimeModeMutation()
  const [error, setError] = useState<string | null>(null)
  const settings = settingsQuery.data
  const isColdLoading = settingsQuery.isPending && !settings

  const runtimeItems = useMemo(() => buildDiagnosticItems(settings?.runtime ?? null, null), [settings?.runtime])
  const preflightItems = useMemo(() => buildPreflightItems(settings?.preflight ?? null), [settings?.preflight])

  async function loadSettings() {
    setError(null)
    try {
      await settingsQuery.refetch()
    } catch {
      setError('Не удалось загрузить настройки')
    }
  }

  async function handleCooldownChange(seconds: number) {
    await handlePolicyPatch({ profile_job_cooldown_seconds: seconds })
  }

  async function handlePolicyPatch(update: ExecutionPolicyUpdate) {
    setError(null)
    try {
      await updatePolicyMutation.mutateAsync(update)
    } catch {
      setError('Не удалось сохранить правила безопасности')
    }
  }

  async function handleTestDcChange(enabled: boolean) {
    setError(null)
    try {
      await updateAuthModeMutation.mutateAsync(enabled)
    } catch {
      setError('Не удалось переключить Test DC')
    }
  }

  if (isColdLoading) {
    return (
      <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center text-sm text-gray-500 shadow-sm">
        Загружаем настройки...
      </section>
    )
  }

  return (
    <div className="fade-in grid gap-4 lg:grid-cols-2">
      {error || (settingsQuery.isError && !settings) ? (
        <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600 lg:col-span-2">
          {error ?? 'Не удалось загрузить настройки'}
        </div>
      ) : null}

      <SettingsCard
        action={
          <button
            aria-label="Обновить настройки"
            className="flex size-8 items-center justify-center rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200"
            onClick={() => void loadSettings()}
            type="button"
          >
            <RefreshCw className={`size-4 ${settingsQuery.isFetching ? 'animate-spin' : ''}`} />
          </button>
        }
        icon={<Server className="size-4 text-navy-400" />}
        title="Система"
      >
        <StatusRows items={runtimeItems} />
      </SettingsCard>

      <SettingsCard icon={<ShieldCheck className="size-4 text-emerald-500" />} title="Готовность live-режима">
        <StatusRows items={preflightItems} />
      </SettingsCard>

      <SettingsCard icon={<ShieldCheck className="size-4 text-emerald-500" />} title="Паузы безопасности">
        {settings?.policy ? (
          <div className="space-y-2">
            <div className="rounded-xl bg-gray-50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
                <span>Пауза между задачами профиля</span>
                <HelpTip
                  label="Пауза между задачами профиля"
                  text="Это минимальная пауза между задачами изменения профиля. Например: если стоит 5 минут, новую задачу профиля нельзя запустить сразу после предыдущей."
                />
              </div>
              <div className="mt-1 text-sm font-semibold text-navy-900">
                {formatCooldown(settings.policy.profile_job_cooldown_seconds)}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[0, ...settings.policy.allowed_profile_job_cooldown_seconds].map((seconds) => (
                  <button
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${
                      settings.policy.profile_job_cooldown_seconds === seconds
                        ? 'border-navy-200 bg-navy-50 text-navy-500'
                        : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'
                    }`}
                    disabled={updatePolicyMutation.isPending}
                    key={seconds}
                    onClick={() => void handleCooldownChange(seconds)}
                    type="button"
                  >
                    {formatCooldown(seconds)}
                  </button>
                ))}
              </div>
            </div>
            {productCooldownControls.map((item) => (
              <CooldownRow
                disabled={updatePolicyMutation.isPending}
                help={item.help}
                key={item.key}
                label={item.label}
                onChange={(seconds) => void handlePolicyPatch({ [item.key]: seconds })}
                value={settings.policy[item.key]}
              />
            ))}
          </div>
        ) : (
          <EmptyState />
        )}
      </SettingsCard>

      <SettingsCard icon={<ShieldCheck className="size-4 text-violet-500" />} title="Расширенные настройки">
        {settings?.authMode ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-3 py-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-navy-900">Тестовая среда Telegram</div>
                <div className="mt-0.5 text-xs text-gray-500">
                  {settings.authMode.tdlib_use_test_dc
                    ? 'Только для разработки. Обычные Telegram-аккаунты здесь не авторизуются.'
                    : 'Обычный Telegram. Для рабочей авторизации держите этот режим.'}
                </div>
              </div>
              <button
                aria-checked={settings.authMode.tdlib_use_test_dc}
                aria-label="Переключить Test DC"
                className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors ${
                  settings.authMode.tdlib_use_test_dc ? 'border-emerald-500 bg-emerald-500' : 'border-gray-300 bg-gray-200'
                } ${updateAuthModeMutation.isPending ? 'opacity-60' : 'hover:border-gray-400'}`}
                disabled={updateAuthModeMutation.isPending}
                onClick={() => void handleTestDcChange(!settings.authMode.tdlib_use_test_dc)}
                role="switch"
                type="button"
              >
                <span
                  className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform ${
                    settings.authMode.tdlib_use_test_dc ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {settings.policy ? (
              <div className="space-y-2 rounded-xl bg-gray-50 px-3 py-2">
                <PolicySelect
                  disabled={updatePolicyMutation.isPending}
                  help="Что делать, если приложение пока не знает, можно ли выполнить действие. Например: музыка ещё не проверялась, поэтому можно только предупредить или запретить реальный запуск."
                  label="Неизвестная возможность"
                  onChange={(value) => void handlePolicyPatch({ unknown_capability_policy: value as UnknownCapabilityPolicy })}
                  options={[
                    ['warning_only', 'Только предупреждать'],
                    ['block_live_execution', 'Блокировать реальный запуск'],
                  ]}
                  value={settings.policy.unknown_capability_policy}
                />
                <PolicySelect
                  disabled={updatePolicyMutation.isPending}
                  help="Что делать после недавней ошибки. Например: если Telegram отказал в смене имени пользователя, можно показать предупреждение или временно поставить это действие на паузу."
                  label="Недавние ошибки"
                  onChange={(value) => void handlePolicyPatch({ recent_failure_policy: value as RecentFailurePolicy })}
                  options={[
                    ['warning_only', 'Только предупреждать'],
                    ['cooldown', 'Создавать паузу'],
                  ]}
                  value={settings.policy.recent_failure_policy}
                />
                <PolicySelect
                  disabled={updatePolicyMutation.isPending}
                  help="Когда нужна свежая проверка аккаунта. Например: если проверка была давно, приложение попросит проверить аккаунт перед реальным запуском."
                  label="Актуальность проверки"
                  onChange={(value) => void handlePolicyPatch({ fresh_validity_required: value as FreshValidityPolicy })}
                  options={[
                    ['never', 'Не требовать'],
                    ['if_stale', 'Если проверка устарела'],
                    ['always_for_live', 'Всегда перед реальным запуском'],
                  ]}
                  value={settings.policy.fresh_validity_required}
                />
                <label className="flex items-center justify-between gap-3 text-xs">
                  <span className="flex items-center gap-1.5 font-medium text-gray-600">
                    <span>Макс. возраст проверки</span>
                    <HelpTip
                      label="Максимальный возраст проверки"
                      text="Сколько минут проверка считается свежей. Например: 30 значит, что проверка старше 30 минут будет считаться устаревшей."
                    />
                  </span>
                  <input
                    className="w-20 rounded-lg border border-gray-200 bg-white px-2 py-1 text-right text-xs font-semibold text-navy-900"
                    disabled={updatePolicyMutation.isPending}
                    min={1}
                    onBlur={(event) =>
                      void handlePolicyPatch({ fresh_validity_max_age_minutes: Number(event.currentTarget.value) })
                    }
                    type="number"
                    defaultValue={settings.policy.fresh_validity_max_age_minutes}
                  />
                </label>
                <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2">
                  <label className="flex items-center justify-between gap-3 text-xs">
                    <span>
                      <span className="flex items-center gap-1.5 font-semibold text-red-700">
                        <span>Ручной разбор жёстких блокировок</span>
                        <HelpTip
                          label="Ручной разбор жёстких блокировок"
                          text="Это не отключает защиту автоматически. Например: если сессия отозвана, задачу всё равно нельзя запускать, пока аккаунт снова не войдёт."
                        />
                      </span>
                      <span className="block text-red-600">
                        Критические блокировки всё равно останутся защищены.
                      </span>
                    </span>
                    <input
                      checked={settings.policy.manual_hard_blocker_override_enabled}
                      disabled={updatePolicyMutation.isPending}
                      onChange={(event) =>
                        void handlePolicyPatch({ manual_hard_blocker_override_enabled: event.currentTarget.checked })
                      }
                      type="checkbox"
                    />
                  </label>
                </div>
                <div className="text-[11px] leading-5 text-gray-500">
                  Всегда защищены: {formatHardBlockers(settings.policy.non_overridable_blockers)}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState />
        )}
      </SettingsCard>
    </div>
  )
}

const productCooldownControls = [
  {
    key: 'profile_update_cooldown_seconds',
    label: 'Профиль',
    help: 'Пауза после изменения текста профиля. Например: имя или описание изменили сейчас, следующую похожую задачу лучше запускать позже.',
  },
  {
    key: 'username_cooldown_seconds',
    label: 'Имя пользователя',
    help: 'Пауза для username. Например: Telegram отказал в имени пользователя, и приложение временно предупреждает перед новой попыткой.',
  },
  {
    key: 'profile_photo_cooldown_seconds',
    label: 'Фото',
    help: 'Пауза для аватара. Например: фото уже меняли недавно, новая попытка будет отмечена как более осторожная.',
  },
  {
    key: 'profile_music_cooldown_seconds',
    label: 'Музыка',
    help: 'Пауза для музыки профиля. Например: загрузка или добавление музыки недавно упали, повтор лучше сделать после паузы.',
  },
  {
    key: 'story_post_cooldown_seconds',
    label: 'Публикация историй',
    help: 'Пауза для публикации историй. Например: был лимит Telegram или ошибка публикации, новая история получит предупреждение или блокировку.',
  },
  {
    key: 'story_delete_cooldown_seconds',
    label: 'Удаление историй',
    help: 'Пауза для удаления историй. Например: Telegram не подтвердил удаление, повтор стоит делать осторожно.',
  },
] as const

function CooldownRow({
  disabled,
  help,
  label,
  onChange,
  value,
}: {
  disabled: boolean
  help: string
  label: string
  onChange: (seconds: number) => void
  value: number
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-3 py-2">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
          <span>{label}</span>
          <HelpTip label={label} text={help} />
        </div>
        <div className="text-[11px] text-gray-400">{formatCooldown(value)}</div>
      </div>
      <select
        className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-semibold text-navy-900"
        disabled={disabled}
        onChange={(event) => onChange(Number(event.currentTarget.value))}
        value={value}
      >
        {[0, 300, 900, 1800, 3600].map((seconds) => (
          <option key={seconds} value={seconds}>
            {formatCooldown(seconds)}
          </option>
        ))}
      </select>
    </div>
  )
}

function PolicySelect({
  disabled,
  help,
  label,
  onChange,
  options,
  value,
}: {
  disabled: boolean
  help: string
  label: string
  onChange: (value: string) => void
  options: Array<[string, string]>
  value: string
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-xs">
      <span className="flex items-center gap-1.5 font-medium text-gray-600">
        <span>{label}</span>
        <HelpTip label={label} text={help} />
      </span>
      <select
        className="max-w-48 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-semibold text-navy-900"
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        {options.map(([optionValue, text]) => (
          <option key={optionValue} value={optionValue}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}

function formatHardBlockers(blockers: string[]): string {
  if (blockers.length === 0) return 'нет'
  return blockers.map((blocker) => hardBlockerLabels[blocker] ?? blocker).join(', ')
}

const hardBlockerLabels: Record<string, string> = {
  AUTH_KEY_UNREGISTERED: 'ключ авторизации недействителен',
  PHONE_NUMBER_BANNED: 'номер заблокирован Telegram',
  SESSION_REVOKED: 'сессия отозвана',
  missing_tdlib_credentials: 'нет данных для подключения TDLib',
  reauth_required: 'нужен повторный вход',
  runtime_broken: 'среда выполнения сломана',
}

function SettingsCard({
  action,
  children,
  icon,
  title,
}: {
  action?: React.ReactNode
  children: React.ReactNode
  icon: React.ReactNode
  title: string
}) {
  return (
    <section className="rounded-xl border border-gray-200/70 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-50">{icon}</div>
          <h2 className="truncate text-sm font-bold text-navy-900">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function StatusRows({ items }: { items: SettingsStatusItem[] }) {
  if (items.length === 0) return <EmptyState />

  return (
    <div className="space-y-1.5">
      {items.map((item) => (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-3 py-2" key={item.key}>
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-xs font-medium text-gray-600">{item.label}</span>
            {item.help ? <HelpTip label={item.label} text={item.help} /> : null}
          </span>
          <span className={`flex items-center gap-1.5 text-[10px] font-semibold ${statusTextClass(item.status)}`}>
            <span className={`size-1.5 rounded-full ${statusDotClass(item.status)}`} />
            <span className="max-w-28 truncate">{item.message}</span>
          </span>
        </div>
      ))}
    </div>
  )
}

function HelpTip({ label, text }: { label: string; text: string }) {
  return (
    <span className="group relative inline-flex shrink-0">
      <button
        aria-label={`Что значит ${label}`}
        className="flex size-4 items-center justify-center rounded-full text-gray-400 transition-colors hover:text-navy-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-navy-200"
        title={text}
        type="button"
      >
        <CircleHelp className="size-3.5" />
      </button>
      <span className="pointer-events-none absolute left-1/2 top-5 z-20 hidden w-64 -translate-x-1/2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium leading-snug text-gray-600 shadow-lg group-hover:block group-focus-within:block">
        {text}
      </span>
    </span>
  )
}

function EmptyState() {
  return <div className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-400">Нет данных</div>
}

function statusDotClass(status: SettingsStatusItem['status']): string {
  if (status === 'ok') return 'bg-emerald-500'
  if (status === 'down') return 'bg-red-500'
  return 'bg-honey-500'
}

function statusTextClass(status: SettingsStatusItem['status']): string {
  if (status === 'ok') return 'text-emerald-700'
  if (status === 'down') return 'text-red-700'
  return 'text-honey-700'
}
