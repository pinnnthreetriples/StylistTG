import { AlertTriangle, X } from 'lucide-react'
import { useState } from 'react'

import { formatChangeOperationLabel, groupRealExecutionChanges, type ChangeItem } from '@/lib/dashboard'
import { validityCheckSummary, type AccountValidityCheck } from '@/lib/accountSafety'
import { compactOperationLogLabel, type OperationLog } from '@/lib/operationLogs'
import {
  proxyErrorLabel,
  proxyStatusLabel,
  type AccountProxy,
  type AccountProxyInput,
} from '@/lib/proxy'

export function SafetyHistoryPanel({ checks }: { checks: AccountValidityCheck[] }) {
  return (
    <section className="mb-4 rounded-xl border border-gray-200 bg-white p-4 shadow-soft" id="account-workspace-debug">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-gray-900">История проверок безопасности</h2>
        <span className="text-[11px] text-gray-400">
          {checks.length > 0 ? `Последние ${Math.min(checks.length, 5)}` : 'Нет проверок'}
        </span>
      </div>
      {checks.length === 0 ? (
        <p className="text-xs text-gray-500">
          Проверка ещё не запускалась. Кнопка “Проверить” не меняет аккаунт, а только проверяет сессию.
        </p>
      ) : (
        <div className="space-y-1.5">
          {checks.slice(0, 5).map((check) => (
            <details className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" key={check.id}>
              <summary className="cursor-pointer font-semibold text-gray-800">{validityCheckSummary(check)}</summary>
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-white p-2 text-[11px] text-gray-500">
                {JSON.stringify({ status: check.status, error_code: check.error_code, details: check.details, result: check.result }, null, 2)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </section>
  )
}

export function ProxyPanel({
  proxy,
  isSaving,
  isChecking,
  isDeleting,
  onSave,
  onCheck,
  onDelete,
}: {
  proxy: AccountProxy | null
  isSaving: boolean
  isChecking: boolean
  isDeleting: boolean
  onSave: (payload: AccountProxyInput) => void
  onCheck: () => void
  onDelete: () => void
}) {
  const [proxyType, setProxyType] = useState<AccountProxyInput['proxy_type']>(proxy?.proxy_type === 'http' ? 'http' : 'socks5')
  const [host, setHost] = useState(proxy?.host ?? '')
  const [port, setPort] = useState(proxy?.port ?? 1080)
  const [username, setUsername] = useState(proxy?.username ?? '')
  const [password, setPassword] = useState('')
  const errorLabel = proxyErrorLabel(proxy?.last_error_code)

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-gray-900">Сеть и Proxy</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            Proxy используется для сетевой маршрутизации аккаунта и диагностики подключения.
          </p>
        </div>
        <span className="rounded-lg bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600">
          {proxyStatusLabel(proxy?.status)}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-[110px_1fr_90px]">
        <select
          className="rounded-lg border border-gray-200 bg-white px-2.5 py-2 text-sm"
          onChange={(event) => setProxyType(event.currentTarget.value as AccountProxyInput['proxy_type'])}
          value={proxyType}
        >
          <option value="socks5">SOCKS5</option>
          <option value="http">HTTP</option>
        </select>
        <input className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm" onChange={(event) => setHost(event.currentTarget.value)} placeholder="host" value={host} />
        <input className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm" onChange={(event) => setPort(Number(event.currentTarget.value))} placeholder="port" type="number" value={port} />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <input className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm" onChange={(event) => setUsername(event.currentTarget.value)} placeholder="username" value={username} />
        <input
          className="rounded-lg border border-gray-200 px-2.5 py-2 text-sm"
          onChange={(event) => setPassword(event.currentTarget.value)}
          placeholder={proxy?.has_password ? 'пароль сохранён, новый ввод заменит его' : 'password'}
          type="password"
          value={password}
        />
      </div>
      {proxy?.last_checked_at || errorLabel ? (
        <p className="mt-2 text-xs text-gray-500">
          {proxy?.last_checked_at ? `Последняя проверка: ${new Date(proxy.last_checked_at).toLocaleString('ru-RU')}` : null}
          {errorLabel ? ` · ${errorLabel}` : null}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="rounded-lg bg-navy-500 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          disabled={isSaving}
          onClick={() => onSave({ proxy_type: proxyType, host, port, username: username || null, password: password || null })}
          type="button"
        >
          {isSaving ? 'Сохраняем…' : 'Сохранить'}
        </button>
        <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 disabled:opacity-50" disabled={!proxy || isChecking} onClick={onCheck} type="button">
          {isChecking ? 'Проверяем…' : 'Проверить proxy'}
        </button>
        <button className="rounded-lg border border-red-100 px-3 py-1.5 text-xs font-semibold text-red-500 disabled:opacity-50" disabled={!proxy || isDeleting} onClick={onDelete} type="button">
          {isDeleting ? 'Удаляем…' : 'Удалить'}
        </button>
      </div>
    </section>
  )
}

export function OperationLogsPanel({ logs, title }: { logs: OperationLog[]; title: string }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-soft">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
        <span className="text-[11px] text-gray-400">{logs.length ? `Событий: ${logs.length}` : 'Нет событий'}</span>
      </div>
      {logs.length === 0 ? (
        <p className="text-xs text-gray-500">Пока нет записей. Новые проверки и операции будут появляться здесь.</p>
      ) : (
        <div className="space-y-1.5">
          {logs.map((log) => (
            <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600" key={log.id}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-gray-800">{compactOperationLogLabel(log)}</span>
                <span className="text-[11px] text-gray-400">{new Date(log.created_at).toLocaleString('ru-RU')}</span>
              </div>
              <p className="mt-0.5 text-gray-500">{log.message}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function RealTelegramExecutionModal({
  changedItems,
  isSubmitting,
  onCancel,
  onConfirm,
}: {
  changedItems: ChangeItem[]
  isSubmitting: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const groups = groupRealExecutionChanges(changedItems)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-navy-900/25 px-4 backdrop-blur-sm">
      <div className="modal-animate w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-gray-100 px-4 py-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="mt-0.5 flex size-8 flex-shrink-0 items-center justify-center rounded-lg bg-honey-50 text-honey-700">
              <AlertTriangle className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-gray-900">Подтвердите изменение аккаунта</h2>
              <p className="mt-1 text-xs leading-relaxed text-gray-500">Это действие реально изменит Telegram-аккаунт.</p>
            </div>
          </div>
          <button
            aria-label="Закрыть подтверждение"
            className="flex size-8 flex-shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-50 hover:text-gray-700"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-3 px-4 py-3">
          <RealExecutionGroup title="Profile" items={groups.profile} />
          <RealExecutionGroup title="Music" items={groups.music} />
          <RealExecutionGroup title="Stories" items={groups.stories} />
        </div>

        <div className="flex justify-end gap-2 border-t border-gray-100 bg-gray-50 px-4 py-3">
          <button className="rounded-lg px-3 py-2 text-xs font-semibold text-gray-500 transition hover:bg-white hover:text-gray-700 disabled:opacity-50" disabled={isSubmitting} onClick={onCancel} type="button">
            Отмена
          </button>
          <button className="rounded-lg bg-navy-400 px-4 py-2 text-xs font-semibold text-white transition hover:bg-navy-500 disabled:opacity-50" disabled={isSubmitting} onClick={onConfirm} type="button">
            Подтвердить и создать задачу
          </button>
        </div>
      </div>
    </div>
  )
}

function RealExecutionGroup({ title, items }: { title: string; items: ChangeItem[] }) {
  if (items.length === 0) return null
  return (
    <section>
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-400">{title}</h3>
      <ul className="mt-1.5 space-y-1">
        {items.map((item) => (
          <li className="flex gap-2 text-xs text-gray-700" key={`${item.operation}:${item.value}`}>
            <span className="mt-1 size-1.5 flex-shrink-0 rounded-full bg-navy-300" />
            <span className="min-w-0">
              <span className="font-semibold">{formatChangeOperationLabel(item.operation)}</span>
              <span className="text-gray-400"> · {item.value}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
