import { AlertTriangle, CheckCircle2, Loader2, Pause, Play, RotateCcw, UserPlus, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@stylisttg/ui'
import {
  createAndStartAuthBatchFromValidation,
  serializeAuthBatchDraft,
} from '@/components/auth/BulkAuthScreen.logic'
import {
  buildAuthBatchPrimaryActionLabel,
  buildAuthBatchValidationMessage,
  buildBackendValidItemLines,
  cancelAuthBatch,
  createAuthBatch,
  fetchAuthBatch,
  labelAuthBatchItemStatus,
  labelAuthBatchStatus,
  parseBulkPhones,
  parseBulkPhoneLines,
  pauseAuthBatch,
  pollAuthBatch,
  resumeAuthBatch,
  retryAuthBatchItem,
  sanitizeBulkPhoneInput,
  startAuthBatch,
  submitAuthBatchCode,
  submitAuthBatchPassword,
  uniqueBulkPhoneLines,
  validBulkPhoneLines,
  validateAuthBatchPhones,
  type AuthBatchItem,
  type AuthBatchSnapshot,
  type AuthBatchValidation,
} from '@/lib/authBatches'
import { normalizeError } from '@/lib/appErrors'
import type { LiveStatus } from '@/lib/liveStatus'
import { labelIssue } from '@/lib/uiLabels'

const LAST_AUTH_BATCH_STORAGE_KEY = 'stylisttg.last_auth_batch_id'
const AUTH_BATCH_DRAFT_STORAGE_KEY = 'stylisttg.auth_batch_draft'

export function BulkAuthScreen({
  liveStatus,
  onTestDcChange,
  testDcEnabled,
  testDcPending,
}: {
  liveStatus: LiveStatus
  onTestDcChange: (enabled: boolean) => void
  testDcEnabled: boolean
  testDcPending: boolean
}) {
  const draft = readDraft()
  const [rawInput, setRawInput] = useState(draft.rawInput)
  const [label, setLabel] = useState(draft.label)
  const [validation, setValidation] = useState<AuthBatchValidation | null>(null)
  const [snapshot, setSnapshot] = useState<AuthBatchSnapshot | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lastPollRef = useRef<string | null>(null)

  const parsedItems = useMemo(() => parseBulkPhones(rawInput), [rawInput])
  const parsedLines = useMemo(() => parseBulkPhoneLines(rawInput), [rawInput])
  const localInvalidRows = parsedLines.filter((line) => line.status === 'invalid')
  const hasLocalErrors = localInvalidRows.length > 0
  const canCreate =
    !isBusy &&
    parsedItems.length > 0 &&
    !hasLocalErrors &&
    (validation === null || validation.valid_items.length > 0)
  const primaryActionLabel = buildAuthBatchPrimaryActionLabel(parsedItems.length)
  const waitingItems = snapshot?.items.filter((item) => item.status === 'waiting_code' || item.status === 'waiting_2fa') ?? []

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(AUTH_BATCH_DRAFT_STORAGE_KEY, serializeAuthBatchDraft(label))
  }, [label])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const batchId = window.localStorage.getItem(LAST_AUTH_BATCH_STORAGE_KEY)
    if (!batchId) return
    void fetchAuthBatch(batchId)
      .then((restored) => {
        lastPollRef.current = restored.server_time
        setSnapshot(restored)
      })
      .catch(() => {
        window.localStorage.removeItem(LAST_AUTH_BATCH_STORAGE_KEY)
      })
  }, [])

  useEffect(() => {
    if (!snapshot?.batch.id || ['completed', 'failed', 'cancelled'].includes(snapshot.batch.status)) return
    const delay = snapshot.poll_again_in_ms || 3000
    const timer = window.setTimeout(() => {
      void pollAuthBatch(snapshot.batch.id, lastPollRef.current)
        .then((next) => {
          lastPollRef.current = next.server_time
          setSnapshot((current) => current ? mergeSnapshot(current, next) : next)
        })
        .catch(() => undefined)
    }, delay)
    return () => window.clearTimeout(timer)
  }, [snapshot])

  async function handleValidate() {
    setIsBusy(true)
    setError(null)
    try {
      const result = await validateAuthBatchPhones(parsedItems)
      setValidation(result)
      setError(buildAuthBatchValidationMessage(result))
      await openActiveBatchFromValidation(result)
    } catch (err) {
      setError(formatBulkError(err))
    } finally {
      setIsBusy(false)
    }
  }

  async function handleCreateAndStart() {
    setIsBusy(true)
    setError(null)
    let createdBatchId: string | null = null
    try {
      const currentValidation = validation ?? await validateAuthBatchPhones(parsedItems)
      setValidation(currentValidation)
      if (await openActiveBatchFromValidation(currentValidation)) {
        setError(buildAuthBatchValidationMessage(currentValidation))
        return
      }
      const validationMessage = buildAuthBatchValidationMessage(currentValidation)
      if (validationMessage) {
        setError(validationMessage)
        return
      }
      const started = await createAndStartAuthBatchFromValidation({
        createBatch: createAuthBatch,
        currentValidation,
        idempotencyKey: crypto.randomUUID(),
        label,
        onCreatedBatch: (batchId) => {
          createdBatchId = batchId
        },
        startBatch: startAuthBatch,
      })
      lastPollRef.current = started.server_time
      rememberBatch(started.batch.id)
      setSnapshot(started)
    } catch (err) {
      if (createdBatchId) {
        await restoreBatchAfterStartError(createdBatchId)
      }
      setError(formatBulkError(err))
    } finally {
      setIsBusy(false)
    }
  }

  async function openActiveBatchFromValidation(result: AuthBatchValidation): Promise<boolean> {
    const batchId = result.active_batch_conflicts.find((item) => item.batch_id)?.batch_id
    if (!batchId) return false
    const activeSnapshot = await fetchAuthBatch(batchId)
    lastPollRef.current = activeSnapshot.server_time
    rememberBatch(activeSnapshot.batch.id)
    setSnapshot(activeSnapshot)
    return true
  }

  async function restoreBatchAfterStartError(batchId: string) {
    try {
      const failedSnapshot = await fetchAuthBatch(batchId)
      lastPollRef.current = failedSnapshot.server_time
      rememberBatch(failedSnapshot.batch.id)
      setSnapshot(failedSnapshot)
    } catch {
      // Keep the visible error from the failed start request.
    }
  }

  async function updateSnapshot(action: () => Promise<AuthBatchSnapshot>) {
    setIsBusy(true)
    setError(null)
    try {
      const next = await action()
      lastPollRef.current = next.server_time
      setSnapshot(next)
    } catch (err) {
      setError(formatBulkError(err))
    } finally {
      setIsBusy(false)
    }
  }

  async function updateItem(action: () => Promise<AuthBatchItem>) {
    try {
      const item = await action()
      setSnapshot((current) => current ? { ...current, items: current.items.map((row) => row.id === item.id ? item : row) } : current)
    } catch (err) {
      setError(formatBulkError(err))
    }
  }

  return (
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-4 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-muted px-2.5 py-1 font-semibold text-primary">Только по вашему действию</span>
            <span className="rounded-full bg-muted px-2.5 py-1 font-semibold text-primary">Запись в аудит</span>
            <span className="rounded-full bg-muted px-2.5 py-1 font-semibold text-primary">Лимиты и блокировки</span>
            <span className={`rounded-full px-2.5 py-1 font-semibold ${liveStatusClassName(liveStatus.tone)}`}>{liveStatus.label}</span>
          </div>
          {testDcEnabled ? (
            <div className="mb-4 rounded-xl border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
              <div className="font-semibold">Включена тестовая среда Telegram</div>
              <div className="mt-1">Обычные Telegram-аккаунты здесь не авторизуются.</div>
              <Button
                className="mt-2"
                disabled={testDcPending}
                onClick={() => void onTestDcChange(false)}
                size="sm"
                type="button"
                variant="secondary"
              >
                Выключить Test DC
              </Button>
            </div>
          ) : null}
          <label className="block text-xs font-semibold uppercase text-muted-foreground" htmlFor="bulk-auth-phones">Номера</label>
          <textarea
            id="bulk-auth-phones"
            aria-label="Номера телефонов"
            className="mt-2 min-h-64 w-full resize-y rounded-xl border border-border px-3 py-2 text-sm leading-6 focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={(e) => {
              setRawInput(sanitizeBulkPhoneInput(e.target.value))
              setValidation(null)
            }}
            placeholder="+79990000001&#10;79990000002, Марина"
            value={rawInput}
          />
          <div className="mt-2 flex flex-wrap items-center gap-1.5 border-b border-border pb-3">
            <Button onClick={() => { setRawInput(uniqueBulkPhoneLines(parsedLines).join('\n')); setValidation(null) }} size="sm" type="button" variant="secondary">
              Уникализировать
            </Button>
            <Button onClick={() => { setRawInput(newLinesOnly(validation, parsedLines).join('\n')); setValidation(null) }} size="sm" type="button" variant="secondary">
              Только новые
            </Button>
            <Button className="ml-auto" onClick={() => { setRawInput(''); setValidation(null) }} size="sm" type="button" variant="ghost">
              Очистить всё
            </Button>
          </div>
          <ValidationSummary localInvalidRows={localInvalidRows} parsedCount={parsedLines.length} validation={validation} />
          <label className="mt-4 block text-xs font-semibold uppercase text-muted-foreground">{parsedItems.length === 1 ? 'Название аккаунта' : 'Название пачки'}</label>
          <input aria-label="Название пачки" className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Необязательно" />
          {error ? <div className="mt-3 rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div> : null}
          <div className="mt-4 flex gap-2">
            <Button className="min-w-28" disabled={isBusy || parsedItems.length === 0} onClick={handleValidate} type="button" variant="secondary">
              Проверить
            </Button>
            <Button
              className="min-w-0 flex-1"
              disabled={!canCreate}
              icon={isBusy ? <Loader2 className="size-4 animate-spin" /> : <UserPlus className="size-4" />}
              onClick={handleCreateAndStart}
              type="button"
            >
              {isBusy ? 'Добавляем...' : primaryActionLabel}
            </Button>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
          {snapshot ? (
            <BatchDashboard
              isBusy={isBusy}
              onCancel={() => void updateSnapshot(() => cancelAuthBatch(snapshot.batch.id))}
              onPause={() => void updateSnapshot(() => pauseAuthBatch(snapshot.batch.id))}
              onResume={() => void updateSnapshot(() => resumeAuthBatch(snapshot.batch.id))}
              onRetryItem={(item) => void updateItem(() => retryAuthBatchItem(snapshot.batch.id, item.id))}
              onSubmitCode={(item, code) => void updateItem(() => submitAuthBatchCode(snapshot.batch.id, item.id, code))}
              onSubmitPassword={(item, password) => void updateItem(() => submitAuthBatchPassword(snapshot.batch.id, item.id, password))}
              snapshot={snapshot}
              waitingItems={waitingItems}
            />
          ) : (
            <BatchPreview lines={parsedLines} />
          )}
        </section>
      </div>
  )
}

function formatBulkError(error: unknown): string {
  const normalized = normalizeError(error)
  return labelIssue(normalized.error_code)
}

function rememberBatch(batchId: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(LAST_AUTH_BATCH_STORAGE_KEY, batchId)
}

function liveStatusClassName(tone: LiveStatus['tone']): string {
  if (tone === 'green') return 'bg-muted text-primary'
  if (tone === 'red') return 'bg-destructive/10 text-destructive'
  if (tone === 'amber') return 'bg-muted text-muted-foreground'
  return 'bg-muted text-muted-foreground'
}

function ValidationSummary({
  localInvalidRows,
  parsedCount,
  validation,
}: {
  localInvalidRows: ReturnType<typeof parseBulkPhoneLines>
  parsedCount: number
  validation: AuthBatchValidation | null
}) {
  const validCount = validation?.valid_items.length ?? Math.max(0, parsedCount - localInvalidRows.length)
  const duplicateCount = validation?.duplicates.length ?? 0
  const existingCount = validation?.existing_accounts.length ?? 0
  const activeConflictCount = validation?.active_batch_conflicts.length ?? 0
  const invalidRows = [
    ...localInvalidRows.map((item) => `Строка ${item.position + 1}: ${item.error}`),
    ...(validation?.invalid_items.map((item) => `Строка ${item.position + 1}: ${item.error}`) ?? []),
  ]

  return (
    <div className="mt-3 space-y-2 text-xs">
      <div className="rounded-lg bg-muted px-3 py-2 font-medium text-muted-foreground">
        Новые <span className="text-foreground">{validCount}</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        Уже есть <span className="text-foreground">{existingCount}</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        Дубли <span className="text-foreground">{duplicateCount}</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        Ошибки{' '}
        <span className={invalidRows.length + activeConflictCount > 0 ? 'text-destructive' : 'text-foreground'}>
          {invalidRows.length + activeConflictCount}
        </span>
      </div>
      {validation ? (
        <>
          <ValidationGroup title="Уже есть" rows={validation.existing_accounts.map((item) => item.phone_number)} tone="warning" />
          <ValidationGroup title="Дубли" rows={validation.duplicates.map((item) => item.phone_number)} tone="muted" />
          <ValidationGroup title="Авторизация уже идёт" rows={validation.active_batch_conflicts.map((item) => item.phone_number)} tone="warning" />
        </>
      ) : null}
      <ValidationGroup title="Ошибки строк" rows={invalidRows} tone="error" />
    </div>
  )
}

function BatchPreview({ lines }: { lines: ReturnType<typeof parseBulkPhoneLines> }) {
  const visibleLines = lines.slice(0, 6)
  const remainingCount = Math.max(0, lines.length - visibleLines.length)

  return (
    <div>
      <div className="border-b border-border pb-4">
        <h2 className="font-sans text-lg font-bold text-foreground">Предпросмотр</h2>
        <p className="mt-1 text-xs text-muted-foreground">Перед запуском проверьте номера и дубли.</p>
      </div>
      {visibleLines.length === 0 ? (
        <div className="flex min-h-72 items-center justify-center text-center text-sm text-muted-foreground">
          Добавьте номера слева.
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-xl border border-border">
          {visibleLines.map((line) => (
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2 last:border-b-0" key={`${line.position}-${line.input}`}>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-foreground">{line.phone_number ?? line.input}</div>
                <div className={`truncate text-xs ${line.status === 'invalid' ? 'text-destructive' : 'text-muted-foreground'}`}>
                  {line.status === 'invalid' ? line.error : line.label || 'Без метки'}
                </div>
              </div>
              <span className={`shrink-0 rounded px-2 py-1 text-[11px] font-semibold ${line.status === 'invalid' ? 'bg-destructive/10 text-destructive' : 'bg-muted text-primary'}`}>
                {line.status === 'invalid' ? 'Ошибка' : 'Готов'}
              </span>
            </div>
          ))}
          {remainingCount > 0 ? (
            <div className="bg-muted px-3 py-2 text-xs font-medium text-muted-foreground">Ещё {remainingCount}</div>
          ) : null}
        </div>
      )}
    </div>
  )
}

function ValidationGroup({ rows, title, tone }: { rows: string[]; title: string; tone: 'error' | 'muted' | 'warning' }) {
  if (rows.length === 0) return null
  const toneClass = tone === 'error' ? 'border-destructive/20 bg-destructive/10 text-destructive' : tone === 'warning' ? 'border-border bg-muted text-muted-foreground' : 'border-border bg-muted text-muted-foreground'
  return (
    <div className={`rounded-lg border px-3 py-2 ${toneClass}`}>
      <div className="font-semibold">{title}</div>
      <div className="mt-1 space-y-0.5">
        {rows.map((row) => <div className="truncate" key={row}>{row}</div>)}
      </div>
    </div>
  )
}

function BatchDashboard({
  isBusy,
  onCancel,
  onPause,
  onResume,
  onRetryItem,
  onSubmitCode,
  onSubmitPassword,
  snapshot,
  waitingItems,
}: {
  isBusy: boolean
  onCancel: () => void
  onPause: () => void
  onResume: () => void
  onRetryItem: (item: AuthBatchItem) => void
  onSubmitCode: (item: AuthBatchItem, code: string) => void
  onSubmitPassword: (item: AuthBatchItem, password: string) => void
  snapshot: AuthBatchSnapshot
  waitingItems: AuthBatchItem[]
}) {
  const batch = snapshot.batch
  const isTerminalBatch = ['completed', 'failed', 'cancelled'].includes(batch.status)
  const isCompleted = batch.status === 'completed'
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <h2 className="font-sans text-lg font-bold text-foreground">{batch.label || 'Новая пачка'}</h2>
          <p className="text-xs text-muted-foreground">{labelAuthBatchStatus(batch.status)} · {batch.success_count}/{batch.total_count} авторизовано</p>
        </div>
        {!isTerminalBatch ? (
          <div className="flex gap-2">
            {batch.status === 'paused' ? (
              <Button disabled={isBusy} icon={<Play className="size-4" />} onClick={onResume} type="button">Продолжить</Button>
            ) : (
              <Button disabled={isBusy} icon={<Pause className="size-4" />} onClick={onPause} type="button" variant="secondary">Пауза</Button>
            )}
            <Button disabled={isBusy} icon={<XCircle className="size-4" />} onClick={onCancel} type="button" variant="danger">Отмена</Button>
          </div>
        ) : null}
      </div>

      {isCompleted ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted px-3 py-3">
          <div>
            <div className="text-sm font-semibold text-primary">Пачка завершена</div>
            <div className="text-xs text-primary">{batch.success_count} из {batch.total_count} аккаунтов готовы</div>
          </div>
        </div>
      ) : null}

      {waitingItems.length > 0 ? (
        <div className="my-4 rounded-xl border border-border bg-muted p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Ожидают ввода</div>
          <div className="space-y-2">
            {waitingItems.map((item) => (
              <CredentialRow item={item} key={item.id} onSubmitCode={onSubmitCode} onSubmitPassword={onSubmitPassword} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 overflow-hidden rounded-xl border border-border">
        {snapshot.items.map((item) => (
          <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2 last:border-b-0" key={item.id}>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-foreground">{authBatchItemPhoneLabel(item)}</div>
              <div className="truncate text-xs text-muted-foreground">{item.label || (item.error_code ? labelIssue(item.error_code) : item.error_message) || 'Без метки'}</div>
            </div>
            <div className="flex items-center gap-2">
              <StatusPill status={item.status} />
              {!isTerminalBatch && ['failed', 'timed_out'].includes(item.status) ? (
                <Button aria-label="Повторить" icon={<RotateCcw className="size-4" />} onClick={() => onRetryItem(item)} size="icon" type="button" variant="ghost" />
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function CredentialRow({ item, onSubmitCode, onSubmitPassword }: { item: AuthBatchItem; onSubmitCode: (item: AuthBatchItem, code: string) => void; onSubmitPassword: (item: AuthBatchItem, password: string) => void }) {
  const [value, setValue] = useState('')
  const isPassword = item.status === 'waiting_2fa'
  return (
    <div className="grid gap-2 rounded-lg bg-card p-2 sm:grid-cols-[1fr_180px_auto] sm:items-center">
      <div className="text-sm font-semibold text-foreground">{authBatchItemPhoneLabel(item)}</div>
      <input aria-label={isPassword ? 'Пароль 2FA' : 'Код Telegram'} className="rounded-lg border border-border px-3 py-2 text-sm" onChange={(e) => setValue(e.target.value)} placeholder={isPassword ? 'Пароль 2FA' : 'Код'} type={isPassword ? 'password' : 'text'} value={value} />
      <Button disabled={value.length < 4} onClick={() => isPassword ? onSubmitPassword(item, value) : onSubmitCode(item, value)} type="button">
        Отправить
      </Button>
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const positive = status === 'authorized'
  const problem = ['failed', 'timed_out', 'cancelled'].includes(status)
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-semibold ${positive ? 'bg-muted text-primary' : problem ? 'bg-destructive/10 text-destructive' : 'bg-muted text-muted-foreground'}`}>
      {positive ? <CheckCircle2 className="size-3" /> : problem ? <AlertTriangle className="size-3" /> : null}
      {labelAuthBatchItemStatus(status)}
    </span>
  )
}

function authBatchItemPhoneLabel(item: AuthBatchItem): string {
  return item.phone_number ?? item.phone_hint
}

function readDraft(): { label: string; rawInput: string } {
  if (typeof window === 'undefined') return { label: '', rawInput: '' }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(AUTH_BATCH_DRAFT_STORAGE_KEY) || '{}') as Record<string, unknown>
    const label = typeof parsed.label === 'string' ? parsed.label : ''
    if ('rawInput' in parsed) {
      window.localStorage.setItem(AUTH_BATCH_DRAFT_STORAGE_KEY, serializeAuthBatchDraft(label))
    }
    return { label, rawInput: '' }
  } catch {
    return { label: '', rawInput: '' }
  }
}

function newLinesOnly(validation: AuthBatchValidation | null, lines: ReturnType<typeof parseBulkPhoneLines>): string[] {
  if (!validation) return validBulkPhoneLines(lines)
  return buildBackendValidItemLines(validation)
}

function mergeSnapshot(current: AuthBatchSnapshot, next: AuthBatchSnapshot): AuthBatchSnapshot {
  const changed = new Map(next.items.map((item) => [item.id, item]))
  return {
    ...next,
    items: current.items.map((item) => changed.get(item.id) ?? item),
  }
}
