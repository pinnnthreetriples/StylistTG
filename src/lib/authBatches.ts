import { apiRequest } from '@/lib/http'

export type AuthBatchPhoneInput = {
  phone_number: string
  label?: string | null
}

export type AuthBatch = {
  id: string
  label: string | null
  status: string
  total_count: number
  success_count: number
  failed_count: number
  cancelled_count: number
  skipped_count: number
  max_running_commands: number
  max_waiting_input: number
  max_total_active: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type AuthBatchItem = {
  id: string
  batch_id: string
  account_id: string
  phone_number: string
  label: string | null
  position: number
  status: string
  attempt_count: number
  resend_count: number
  code_error_count: number
  password_error_count: number
  code_expires_at: string | null
  next_retry_at: string | null
  error_code: string | null
  error_message: string | null
  updated_at: string
  authorized_at: string | null
}

export type AuthBatchSnapshot = {
  batch: AuthBatch
  items: AuthBatchItem[]
  server_time: string
  poll_again_in_ms: number
}

export type AuthBatchValidation = {
  valid_items: Array<{ phone_number: string; label: string | null; position: number }>
  invalid_items: Array<{ input: string; label: string | null; position: number; error: string }>
  duplicates: Array<{ phone_number: string; label: string | null; position: number; account_id: string | null; batch_item_id: string | null; batch_id: string | null }>
  existing_accounts: Array<{ phone_number: string; label: string | null; position: number; account_id: string | null; batch_item_id: string | null; batch_id: string | null }>
  active_batch_conflicts: Array<{ phone_number: string; label: string | null; position: number; account_id: string | null; batch_item_id: string | null; batch_id: string | null }>
}

export type ParsedBulkPhoneLine = {
  input: string
  phone_number: string | null
  label: string | null
  position: number
  status: 'valid' | 'invalid'
  error: string | null
}

export function parseBulkPhones(input: string): AuthBatchPhoneInput[] {
  return parseBulkPhoneLines(input)
    .filter((line) => line.status === 'valid' && line.phone_number)
    .map((line) => ({ phone_number: line.phone_number as string, label: line.label }))
}

export function parseBulkPhoneLines(input: string): ParsedBulkPhoneLine[] {
  return sanitizeBulkPhoneInput(input)
    .split(/\r?\n/)
    .map((line, index) => ({ input: line.trim(), index }))
    .filter((line) => line.input)
    .map(({ input, index }) => {
      const [phoneInput, ...labelParts] = input.split(',').map((part) => part.trim())
      const label = labelParts.join(', ') || null
      const normalized = normalizeBulkPhone(phoneInput)
      return {
        input,
        phone_number: normalized.phoneNumber,
        label,
        position: index,
        status: normalized.error ? 'invalid' : 'valid',
        error: normalized.error,
      }
    })
}

export function sanitizeBulkPhoneInput(input: string): string {
  return input
    .split(/\r?\n/)
    .map((line) => sanitizeBulkPhoneLine(line))
    .join('\n')
}

function sanitizeBulkPhoneLine(line: string): string {
  const commaIndex = line.indexOf(',')
  const rawPhone = commaIndex >= 0 ? line.slice(0, commaIndex) : line
  const rawLabel = commaIndex >= 0 ? line.slice(commaIndex + 1).trim() : ''
  const phone = normalizePhoneText(rawPhone)
  if (!phone) return ''
  return rawLabel ? `${phone}, ${rawLabel}` : phone
}

function normalizePhoneText(input: string): string {
  const hasLeadingPlus = input.trimStart().startsWith('+')
  const digits = input.replace(/\D/g, '').slice(0, 15)
  if (!digits) return hasLeadingPlus ? '+' : ''
  if (digits.length === 11 && digits.startsWith('8')) {
    return `+7${digits.slice(1)}`
  }
  if (digits.length === 11 && digits.startsWith('7')) {
    return `+${digits}`
  }
  return `+${digits}`
}

function normalizeBulkPhone(input: string): { phoneNumber: string | null; error: string | null } {
  const compact = normalizePhoneText(input)
  if (/^\+\d{10,15}$/.test(compact)) {
    return { phoneNumber: compact, error: null }
  }
  const digits = compact.replace(/\D/g, '')
  if (digits.length < 10) {
    return { phoneNumber: null, error: 'Короткий номер' }
  }
  if (digits.length > 15) {
    return { phoneNumber: null, error: 'Слишком длинный номер' }
  }
  return { phoneNumber: null, error: 'Нужен международный формат телефона' }
}

export function formatBulkPhoneLine(phoneNumber: string, label: string | null): string {
  return label ? `${phoneNumber}, ${label}` : phoneNumber
}

export function validBulkPhoneLines(lines: ParsedBulkPhoneLine[]): string[] {
  return lines
    .filter((line) => line.status === 'valid' && line.phone_number)
    .map((line) => formatBulkPhoneLine(line.phone_number as string, line.label))
}

export function uniqueBulkPhoneLines(lines: ParsedBulkPhoneLine[]): string[] {
  const seen = new Set<string>()
  return lines
    .filter((line) => line.status === 'valid' && line.phone_number)
    .filter((line) => {
      const phone = line.phone_number as string
      if (seen.has(phone)) return false
      seen.add(phone)
      return true
    })
    .map((line) => formatBulkPhoneLine(line.phone_number as string, line.label))
}

export function buildBackendValidItemLines(validation: AuthBatchValidation | null): string[] {
  return validation?.valid_items.map((item) => formatBulkPhoneLine(item.phone_number, item.label)) ?? []
}

export function buildAuthBatchPrimaryActionLabel(count: number): string {
  return count === 1 ? 'Добавить аккаунт' : 'Добавить аккаунты'
}

const batchStatusLabels: Record<string, string> = {
  pending: 'Ожидает запуска',
  running: 'В работе',
  paused: 'Пауза',
  completed: 'Завершено',
  failed: 'Ошибка',
  cancelled: 'Отменён',
}

const batchItemStatusLabels: Record<string, string> = {
  queued: 'В очереди',
  starting: 'Запуск',
  waiting_code: 'Ожидает код',
  waiting_2fa: 'Ожидает 2FA',
  authorized: 'Готово',
  failed: 'Ошибка',
  timed_out: 'Таймаут',
  cancelled: 'Отменён',
  skipped: 'Пропущен',
  running: 'В работе',
  paused: 'Пауза',
  pending: 'Ожидает',
}

export function labelAuthBatchStatus(status: string): string {
  return batchStatusLabels[status] ?? status
}

export function labelAuthBatchItemStatus(status: string): string {
  return batchItemStatusLabels[status] ?? status
}

export function buildAuthBatchValidationMessage(validation: AuthBatchValidation): string | null {
  if (validation.valid_items.length > 0) return null
  if (validation.existing_accounts.length > 0) {
    const count = validation.existing_accounts.length
    return count === 1
      ? 'Такой аккаунт уже есть. Введите новый номер или откройте существующий аккаунт в списке.'
      : `Эти аккаунты уже есть: ${count}. Оставьте только новые номера.`
  }
  if (validation.active_batch_conflicts.length > 0) {
    return 'По этому номеру уже идёт авторизация. Открываю активную пачку.'
  }
  if (validation.duplicates.length > 0) {
    return 'В списке остались только дубли. Удалите повторяющиеся номера и добавьте хотя бы один новый.'
  }
  if (validation.invalid_items.length > 0) {
    return 'Не найдено ни одного корректного нового номера. Проверьте формат телефонов.'
  }
  return 'Добавьте хотя бы один новый номер.'
}

export async function validateAuthBatchPhones(items: AuthBatchPhoneInput[]): Promise<AuthBatchValidation> {
  return apiRequest<AuthBatchValidation>('/api/auth-batches/validate-phones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
}

export async function createAuthBatch(payload: {
  idempotency_key: string
  label?: string | null
  items: AuthBatchPhoneInput[]
  max_running_commands: number
  max_waiting_input: number
  max_total_active: number
}): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>('/api/auth-batches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function startAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}/start`, { method: 'POST' })
}

export async function fetchAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}`)
}

export async function pauseAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}/pause`, { method: 'POST' })
}

export async function resumeAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}/resume`, { method: 'POST' })
}

export async function cancelAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}/cancel`, { method: 'POST' })
}

export async function pollAuthBatch(batchId: string, updatedSince?: string | null): Promise<AuthBatchSnapshot> {
  const qs = updatedSince ? `?updated_since=${encodeURIComponent(updatedSince)}` : ''
  return apiRequest<AuthBatchSnapshot>(`/api/auth-batches/${batchId}/poll${qs}`)
}

export async function submitAuthBatchCode(batchId: string, itemId: string, code: string): Promise<AuthBatchItem> {
  return apiRequest<AuthBatchItem>(`/api/auth-batches/${batchId}/items/${itemId}/submit-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, idempotency_key: crypto.randomUUID() }),
  })
}

export async function submitAuthBatchPassword(batchId: string, itemId: string, password: string): Promise<AuthBatchItem> {
  return apiRequest<AuthBatchItem>(`/api/auth-batches/${batchId}/items/${itemId}/submit-2fa`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password, idempotency_key: crypto.randomUUID() }),
  })
}

export async function retryAuthBatchItem(batchId: string, itemId: string): Promise<AuthBatchItem> {
  return apiRequest<AuthBatchItem>(`/api/auth-batches/${batchId}/items/${itemId}/retry`, { method: 'POST' })
}
