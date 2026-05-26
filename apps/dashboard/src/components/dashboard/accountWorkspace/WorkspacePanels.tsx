import { AlertTriangle, X } from 'lucide-react'
import { useState } from 'react'
import { Button, FormField, Input, Select } from '@stylisttg/ui'

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
    <section className="mb-4 rounded-xl border border-border bg-card p-4 shadow-sm" id="account-workspace-debug">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-foreground">История проверок безопасности</h2>
        <span className="text-[11px] text-muted-foreground">
          {checks.length > 0 ? `Последние ${Math.min(checks.length, 5)}` : 'Нет проверок'}
        </span>
      </div>
      {checks.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Проверка ещё не запускалась. Кнопка “Проверить” не меняет аккаунт, а только проверяет сессию.
        </p>
      ) : (
        <div className="space-y-1.5">
          {checks.slice(0, 5).map((check) => (
            <details className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground" key={check.id}>
              <summary className="cursor-pointer font-semibold text-foreground">{validityCheckSummary(check)}</summary>
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-card p-2 text-[11px] text-muted-foreground">
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
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-foreground">Сеть и прокси</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Прокси используется для сетевой маршрутизации аккаунта и диагностики подключения.
          </p>
        </div>
        <span className="rounded-lg bg-muted px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
          {proxyStatusLabel(proxy?.status)}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-[150px_1fr_120px]">
        <FormField label="Тип прокси">
          <Select
            onChange={(event) => setProxyType(event.currentTarget.value as AccountProxyInput['proxy_type'])}
            value={proxyType}
          >
            <option value="socks5">SOCKS5</option>
            <option value="http">HTTP</option>
          </Select>
        </FormField>
        <FormField label="Хост">
          <Input onChange={(event) => setHost(event.currentTarget.value)} placeholder="proxy.example.com" value={host} />
        </FormField>
        <FormField label="Порт">
          <Input onChange={(event) => setPort(Number(event.currentTarget.value))} placeholder="1080" type="number" value={port} />
        </FormField>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <FormField label="Логин">
          <Input onChange={(event) => setUsername(event.currentTarget.value)} placeholder="Логин прокси" value={username} />
        </FormField>
        <FormField label="Пароль" hint="Оставьте пустым, чтобы не менять пароль">
          <Input
            autoComplete="new-password"
            onChange={(event) => setPassword(event.currentTarget.value)}
            placeholder={proxy?.has_password ? 'Пароль уже сохранён' : 'Пароль прокси'}
            type="password"
            value={password}
          />
        </FormField>
      </div>
      {proxy?.last_checked_at || errorLabel ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {proxy?.last_checked_at ? `Последняя проверка: ${new Date(proxy.last_checked_at).toLocaleString('ru-RU')}` : null}
          {errorLabel ? ` · ${errorLabel}` : null}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          disabled={isSaving}
          onClick={() => {
            onSave({ proxy_type: proxyType, host, port, username: username || null, password: password || null })
            setPassword('')
          }}
          type="button"
        >
          {isSaving ? 'Сохраняем…' : 'Сохранить'}
        </Button>
        <Button disabled={!proxy || isChecking} onClick={onCheck} type="button" variant="secondary">
          {isChecking ? 'Проверяем…' : 'Проверить прокси'}
        </Button>
        <Button disabled={!proxy || isDeleting} onClick={onDelete} type="button" variant="danger">
          {isDeleting ? 'Удаляем…' : 'Удалить'}
        </Button>
      </div>
    </section>
  )
}

export function OperationLogsPanel({ logs, title }: { logs: OperationLog[]; title: string }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-foreground">{title}</h2>
        <span className="text-[11px] text-muted-foreground">{logs.length ? `Событий: ${logs.length}` : 'Нет событий'}</span>
      </div>
      {logs.length === 0 ? (
        <p className="text-xs text-muted-foreground">Пока нет записей. Новые проверки и операции будут появляться здесь.</p>
      ) : (
        <div className="space-y-1.5">
          {logs.map((log) => (
            <div className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground" key={log.id}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-foreground">{compactOperationLogLabel(log)}</span>
                <span className="text-[11px] text-muted-foreground">{new Date(log.created_at).toLocaleString('ru-RU')}</span>
              </div>
              <p className="mt-0.5 text-muted-foreground">{log.message}</p>
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
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/25 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-card shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="mt-0.5 flex size-8 flex-shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <AlertTriangle className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-foreground">Подтвердите изменение аккаунта</h2>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">Это действие реально изменит Telegram-аккаунт.</p>
            </div>
          </div>
          <button
            aria-label="Закрыть подтверждение"
            className="flex size-8 flex-shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
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

        <div className="flex justify-end gap-2 border-t border-border bg-muted px-4 py-3">
          <button className="rounded-lg px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-card hover:text-foreground disabled:opacity-50" disabled={isSubmitting} onClick={onCancel} type="button">
            Отмена
          </button>
          <button className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary disabled:opacity-50" disabled={isSubmitting} onClick={onConfirm} type="button">
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
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{title}</h3>
      <ul className="mt-1.5 space-y-1">
        {items.map((item) => (
          <li className="flex gap-2 text-xs text-foreground" key={`${item.operation}:${item.value}`}>
            <span className="mt-1 size-1.5 flex-shrink-0 rounded-full bg-primary" />
            <span className="min-w-0">
              <span className="font-semibold">{formatChangeOperationLabel(item.operation)}</span>
              <span className="text-muted-foreground"> · {item.value}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
