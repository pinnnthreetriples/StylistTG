import { CircleHelp, RefreshCw, Server, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type React from 'react'

import {
  fetchExecutionPolicy,
  fetchLivePreflight,
  fetchRuntimeDiagnostics,
  updateExecutionPolicy,
  type ExecutionPolicy,
} from '@/lib/api'
import { fetchAuthRuntimeMode, updateAuthRuntimeMode, type AuthRuntimeMode } from '@/lib/auth'
import { buildDiagnosticItems, type RuntimeDiagnostics } from '@/lib/diagnostics'
import { buildPreflightItems, formatCooldown, type LivePreflight, type SettingsStatusItem } from '@/lib/settings'

export function SettingsPanel() {
  const [runtime, setRuntime] = useState<RuntimeDiagnostics | null>(null)
  const [preflight, setPreflight] = useState<LivePreflight | null>(null)
  const [policy, setPolicy] = useState<ExecutionPolicy | null>(null)
  const [authMode, setAuthMode] = useState<AuthRuntimeMode | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSavingPolicy, setIsSavingPolicy] = useState(false)
  const [isSavingAuthMode, setIsSavingAuthMode] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runtimeItems = useMemo(() => buildDiagnosticItems(runtime, null), [runtime])
  const preflightItems = useMemo(() => buildPreflightItems(preflight), [preflight])

  async function fetchSettings() {
    return Promise.all([
      fetchRuntimeDiagnostics(),
      fetchLivePreflight(),
      fetchExecutionPolicy(),
      fetchAuthRuntimeMode(),
    ])
  }

  async function loadSettings() {
    setIsLoading(true)
    setError(null)
    try {
      const [nextRuntime, nextPreflight, nextPolicy, nextAuthMode] = await fetchSettings()
      setRuntime(nextRuntime)
      setPreflight(nextPreflight)
      setPolicy(nextPolicy)
      setAuthMode(nextAuthMode)
    } catch {
      setError('Не удалось загрузить настройки')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleCooldownChange(seconds: number) {
    setIsSavingPolicy(true)
    setError(null)
    try {
      setPolicy(await updateExecutionPolicy(seconds))
    } catch {
      setError('Не удалось сохранить cooldown')
    } finally {
      setIsSavingPolicy(false)
    }
  }

  async function handleTestDcChange(enabled: boolean) {
    setIsSavingAuthMode(true)
    setError(null)
    try {
      setAuthMode(await updateAuthRuntimeMode(enabled))
    } catch {
      setError('Не удалось переключить Test DC')
    } finally {
      setIsSavingAuthMode(false)
    }
  }

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const [nextRuntime, nextPreflight, nextPolicy, nextAuthMode] = await fetchSettings()
        if (!active) return
        setRuntime(nextRuntime)
        setPreflight(nextPreflight)
        setPolicy(nextPolicy)
        setAuthMode(nextAuthMode)
      } catch {
        if (active) setError('Не удалось загрузить настройки')
      } finally {
        if (active) setIsLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [])

  if (isLoading) {
    return (
      <section className="fade-in rounded-xl border border-gray-200/70 bg-white p-8 text-center text-sm text-gray-500 shadow-sm">
        Загружаем настройки...
      </section>
    )
  }

  return (
    <div className="fade-in grid gap-4 lg:grid-cols-2">
      {error ? (
        <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600 lg:col-span-2">
          {error}
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
            <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} />
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

      <SettingsCard icon={<SlidersHorizontal className="size-4 text-honey-500" />} title="Очередь и задачи">
        {policy ? (
          <div className="space-y-3">
            <div className="rounded-xl bg-gray-50 px-3 py-2">
              <div className="text-xs font-medium text-gray-500">Cooldown задач профиля</div>
              <div className="mt-1 text-sm font-semibold text-navy-900">
                {formatCooldown(policy.profile_job_cooldown_seconds)}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[0, ...policy.allowed_profile_job_cooldown_seconds].map((seconds) => (
                <button
                  className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${
                    policy.profile_job_cooldown_seconds === seconds
                      ? 'border-navy-200 bg-navy-50 text-navy-500'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                  disabled={isSavingPolicy}
                  key={seconds}
                  onClick={() => void handleCooldownChange(seconds)}
                  type="button"
                >
                  {formatCooldown(seconds)}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </SettingsCard>

      <SettingsCard icon={<ShieldCheck className="size-4 text-violet-500" />} title="Расширенные настройки">
        {authMode ? (
          <div className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-3 py-2">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-navy-900">Тестовая среда Telegram</div>
              <div className="mt-0.5 text-xs text-gray-500">
                {authMode.tdlib_use_test_dc
                  ? 'Только для разработки. Обычные Telegram-аккаунты здесь не авторизуются.'
                  : 'Обычный Telegram. Для рабочей авторизации держите этот режим.'}
              </div>
            </div>
            <button
              aria-checked={authMode.tdlib_use_test_dc}
              aria-label="Переключить Test DC"
              className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors ${
                authMode.tdlib_use_test_dc ? 'border-emerald-500 bg-emerald-500' : 'border-gray-300 bg-gray-200'
              } ${isSavingAuthMode ? 'opacity-60' : 'hover:border-gray-400'}`}
              disabled={isSavingAuthMode}
              onClick={() => void handleTestDcChange(!authMode.tdlib_use_test_dc)}
              role="switch"
              type="button"
            >
              <span
                className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform ${
                  authMode.tdlib_use_test_dc ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        ) : (
          <EmptyState />
        )}
      </SettingsCard>
    </div>
  )
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
