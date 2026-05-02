import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, Pause, Play, RotateCcw, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

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
import { labelIssue } from '@/lib/uiLabels'

const LAST_AUTH_BATCH_STORAGE_KEY = 'stylisttg.last_auth_batch_id'
const AUTH_BATCH_DRAFT_STORAGE_KEY = 'stylisttg.auth_batch_draft'

export function BulkAuthScreen({
  onBack,
  onTestDcChange,
  testDcEnabled,
  testDcPending,
}: {
  onBack: () => void
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
    window.localStorage.setItem(AUTH_BATCH_DRAFT_STORAGE_KEY, JSON.stringify({ label, rawInput }))
  }, [label, rawInput])

  useEffect(() => {
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
      const created = await createAuthBatch({
        idempotency_key: crypto.randomUUID(),
        label: label || null,
        items: currentValidation.valid_items.map((item) => ({ phone_number: item.phone_number, label: item.label })),
        max_running_commands: 2,
        max_waiting_input: 5,
        max_total_active: 6,
      })
      createdBatchId = created.batch.id
      const started = await startAuthBatch(created.batch.id)
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
    <div className="min-h-screen bg-cream">
      <header className="sticky top-0 z-40 border-b border-gray-200/70 bg-white">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-5">
          <button className="flex size-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100" onClick={onBack} type="button">
            <ArrowLeft className="size-4" />
          </button>
          <div>
            <h1 className="font-display text-base font-bold text-navy-900">Добавление аккаунтов</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-4 px-5 py-5 lg:grid-cols-[360px_1fr]">
        <section className="rounded-xl border border-gray-200/70 bg-white p-4 shadow-soft">
          {testDcEnabled ? (
            <div className="mb-4 rounded-xl border border-honey-100 bg-honey-50 px-3 py-2 text-xs text-honey-700">
              <div className="font-semibold">Включена тестовая среда Telegram</div>
              <div className="mt-1">Обычные Telegram-аккаунты здесь не авторизуются.</div>
              <button
                className="mt-2 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-honey-700 shadow-sm disabled:opacity-60"
                disabled={testDcPending}
                onClick={() => void onTestDcChange(false)}
                type="button"
              >
                Выключить Test DC
              </button>
            </div>
          ) : null}
          <label className="block text-xs font-semibold uppercase text-gray-400">Номера</label>
          <textarea
            className="mt-2 min-h-64 w-full resize-y rounded-xl border border-gray-200 px-3 py-2 text-sm leading-6 focus:border-navy-300 focus:outline-none focus:ring-2 focus:ring-navy-100"
            onChange={(e) => {
              setRawInput(sanitizeBulkPhoneInput(e.target.value))
              setValidation(null)
            }}
            placeholder="+79990000001&#10;79990000002, Марина"
            value={rawInput}
          />
          <div className="mt-2 flex flex-wrap items-center gap-1.5 border-b border-gray-100 pb-3">
            <button className="rounded-full border border-gray-200 px-2.5 py-1 text-[11px] font-semibold text-gray-500 hover:bg-gray-50" onClick={() => { setRawInput(uniqueBulkPhoneLines(parsedLines).join('\n')); setValidation(null) }} type="button">
              Уникализировать
            </button>
            <button className="rounded-full border border-gray-200 px-2.5 py-1 text-[11px] font-semibold text-gray-500 hover:bg-gray-50" onClick={() => { setRawInput(newLinesOnly(validation, parsedLines).join('\n')); setValidation(null) }} type="button">
              Только новые
            </button>
            <button className="ml-auto rounded-full px-2.5 py-1 text-[11px] font-semibold text-gray-400 hover:bg-gray-50 hover:text-gray-600" onClick={() => { setRawInput(''); setValidation(null) }} type="button">
              Очистить всё
            </button>
          </div>
          <ValidationSummary localInvalidRows={localInvalidRows} parsedCount={parsedLines.length} validation={validation} />
          <label className="mt-4 block text-xs font-semibold uppercase text-gray-400">Название пачки</label>
          <input className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-navy-300 focus:outline-none focus:ring-2 focus:ring-navy-100" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Необязательно" />
          {error ? <div className="mt-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-600">{error}</div> : null}
          <div className="mt-4 flex gap-2">
            <button className="min-w-28 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50" disabled={isBusy || parsedItems.length === 0} onClick={handleValidate} type="button">
              Проверить
            </button>
            <button className="flex-1 rounded-lg bg-navy-400 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!canCreate} onClick={handleCreateAndStart} type="button">
              {isBusy ? <Loader2 className="mx-auto size-4 animate-spin" /> : primaryActionLabel}
            </button>
          </div>
        </section>

        <section className="rounded-xl border border-gray-200/70 bg-white p-4 shadow-soft">
          {snapshot ? (
            <BatchDashboard
              isBusy={isBusy}
              onCancel={() => void updateSnapshot(() => cancelAuthBatch(snapshot.batch.id))}
              onPause={() => void updateSnapshot(() => pauseAuthBatch(snapshot.batch.id))}
              onResume={() => void updateSnapshot(() => resumeAuthBatch(snapshot.batch.id))}
              onRetryItem={(item) => void updateItem(() => retryAuthBatchItem(snapshot.batch.id, item.id))}
              onSubmitCode={(item, code) => void updateItem(() => submitAuthBatchCode(snapshot.batch.id, item.id, code))}
              onSubmitPassword={(item, password) => void updateItem(() => submitAuthBatchPassword(snapshot.batch.id, item.id, password))}
              onBackToAccounts={onBack}
              snapshot={snapshot}
              waitingItems={waitingItems}
            />
          ) : (
            <BatchPreview lines={parsedLines} />
          )}
        </section>
      </main>
    </div>
  )
}

function formatBulkError(error: unknown): string {
  const normalized = normalizeError(error)
  return labelIssue(normalized.error_code)
}

function rememberBatch(batchId: string) {
  window.localStorage.setItem(LAST_AUTH_BATCH_STORAGE_KEY, batchId)
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
      <div className="rounded-lg bg-gray-50 px-3 py-2 font-medium text-gray-500">
        Новые <span className="text-navy-900">{validCount}</span>
        <span className="mx-1.5 text-gray-300">·</span>
        Уже есть <span className="text-navy-900">{existingCount}</span>
        <span className="mx-1.5 text-gray-300">·</span>
        Дубли <span className="text-navy-900">{duplicateCount}</span>
        <span className="mx-1.5 text-gray-300">·</span>
        Ошибки{' '}
        <span className={invalidRows.length + activeConflictCount > 0 ? 'text-red-600' : 'text-navy-900'}>
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
      <div className="border-b border-gray-100 pb-4">
        <h2 className="font-display text-lg font-bold text-navy-900">Предпросмотр</h2>
        <p className="mt-1 text-xs text-gray-400">Перед запуском проверьте номера и дубли.</p>
      </div>
      {visibleLines.length === 0 ? (
        <div className="flex min-h-72 items-center justify-center text-center text-sm text-gray-400">
          Добавьте номера слева.
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-xl border border-gray-100">
          {visibleLines.map((line) => (
            <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2 last:border-b-0" key={`${line.position}-${line.input}`}>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-navy-900">{line.phone_number ?? line.input}</div>
                <div className={`truncate text-xs ${line.status === 'invalid' ? 'text-red-500' : 'text-gray-400'}`}>
                  {line.status === 'invalid' ? line.error : line.label || 'Без метки'}
                </div>
              </div>
              <span className={`shrink-0 rounded px-2 py-1 text-[11px] font-semibold ${line.status === 'invalid' ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700'}`}>
                {line.status === 'invalid' ? 'Ошибка' : 'Готов'}
              </span>
            </div>
          ))}
          {remainingCount > 0 ? (
            <div className="bg-gray-50 px-3 py-2 text-xs font-medium text-gray-400">Ещё {remainingCount}</div>
          ) : null}
        </div>
      )}
    </div>
  )
}

function ValidationGroup({ rows, title, tone }: { rows: string[]; title: string; tone: 'error' | 'muted' | 'warning' }) {
  if (rows.length === 0) return null
  const toneClass = tone === 'error' ? 'border-red-100 bg-red-50 text-red-700' : tone === 'warning' ? 'border-honey-100 bg-honey-50 text-honey-700' : 'border-gray-100 bg-gray-50 text-gray-500'
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
  onBackToAccounts,
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
  onBackToAccounts: () => void
  snapshot: AuthBatchSnapshot
  waitingItems: AuthBatchItem[]
}) {
  const batch = snapshot.batch
  const isTerminalBatch = ['completed', 'failed', 'cancelled'].includes(batch.status)
  const isCompleted = batch.status === 'completed'
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-4">
        <div>
          <h2 className="font-display text-lg font-bold text-navy-900">{batch.label || 'Новая пачка'}</h2>
          <p className="text-xs text-gray-400">{labelAuthBatchStatus(batch.status)} · {batch.success_count}/{batch.total_count} авторизовано</p>
        </div>
        {!isTerminalBatch ? (
          <div className="flex gap-2">
            {batch.status === 'paused' ? (
              <button className="rounded-lg bg-navy-400 px-3 py-2 text-sm font-semibold text-white" disabled={isBusy} onClick={onResume} type="button"><Play className="mr-1 inline size-4" />Продолжить</button>
            ) : (
              <button className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600" disabled={isBusy} onClick={onPause} type="button"><Pause className="mr-1 inline size-4" />Пауза</button>
            )}
            <button className="rounded-lg border border-red-100 px-3 py-2 text-sm font-semibold text-red-600" disabled={isBusy} onClick={onCancel} type="button"><XCircle className="mr-1 inline size-4" />Отмена</button>
          </div>
        ) : null}
      </div>

      {isCompleted ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-3">
          <div>
            <div className="text-sm font-semibold text-emerald-800">Пачка завершена</div>
            <div className="text-xs text-emerald-700">{batch.success_count} из {batch.total_count} аккаунтов готовы</div>
          </div>
          <button className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-emerald-700 shadow-sm hover:bg-emerald-50" onClick={onBackToAccounts} type="button">
            К списку аккаунтов
          </button>
        </div>
      ) : null}

      {waitingItems.length > 0 ? (
        <div className="my-4 rounded-xl border border-honey-100 bg-honey-50/50 p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-honey-600">Ожидают ввода</div>
          <div className="space-y-2">
            {waitingItems.map((item) => (
              <CredentialRow item={item} key={item.id} onSubmitCode={onSubmitCode} onSubmitPassword={onSubmitPassword} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 overflow-hidden rounded-xl border border-gray-100">
        {snapshot.items.map((item) => (
          <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-2 last:border-b-0" key={item.id}>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-navy-900">{item.phone_number}</div>
              <div className="truncate text-xs text-gray-400">{item.label || (item.error_code ? labelIssue(item.error_code) : item.error_message) || 'Без метки'}</div>
            </div>
            <div className="flex items-center gap-2">
              <StatusPill status={item.status} />
              {!isTerminalBatch && ['failed', 'timed_out'].includes(item.status) ? (
                <button className="flex size-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100" onClick={() => onRetryItem(item)} type="button"><RotateCcw className="size-4" /></button>
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
    <div className="grid gap-2 rounded-lg bg-white p-2 sm:grid-cols-[1fr_180px_auto] sm:items-center">
      <div className="text-sm font-semibold text-navy-900">{item.phone_number}</div>
      <input className="rounded-lg border border-gray-200 px-3 py-2 text-sm" onChange={(e) => setValue(e.target.value)} placeholder={isPassword ? 'Пароль 2FA' : 'Код'} type={isPassword ? 'password' : 'text'} value={value} />
      <button className="rounded-lg bg-navy-400 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={value.length < 4} onClick={() => isPassword ? onSubmitPassword(item, value) : onSubmitCode(item, value)} type="button">
        Отправить
      </button>
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const positive = status === 'authorized'
  const problem = ['failed', 'timed_out', 'cancelled'].includes(status)
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-semibold ${positive ? 'bg-emerald-50 text-emerald-700' : problem ? 'bg-red-50 text-red-600' : 'bg-gray-50 text-gray-500'}`}>
      {positive ? <CheckCircle2 className="size-3" /> : problem ? <AlertTriangle className="size-3" /> : null}
      {labelAuthBatchItemStatus(status)}
    </span>
  )
}

function readDraft(): { label: string; rawInput: string } {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(AUTH_BATCH_DRAFT_STORAGE_KEY) || '{}') as Partial<{ label: string; rawInput: string }>
    return { label: parsed.label ?? '', rawInput: parsed.rawInput ?? '' }
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
