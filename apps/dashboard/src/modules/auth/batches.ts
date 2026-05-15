import {
  cancelAuthBatch as cancelTypedAuthBatch,
  createAuthBatch as createTypedAuthBatch,
  fetchAuthBatch as fetchTypedAuthBatch,
  pauseAuthBatch as pauseTypedAuthBatch,
  pollAuthBatch as pollTypedAuthBatch,
  resumeAuthBatch as resumeTypedAuthBatch,
  retryAuthBatchItem as retryTypedAuthBatchItem,
  startAuthBatch as startTypedAuthBatch,
  submitAuthBatchCode as submitTypedAuthBatchCode,
  submitAuthBatchPassword as submitTypedAuthBatchPassword,
  validateAuthBatchPhones as validateTypedAuthBatchPhones,
  type AuthBatchItem as TypedAuthBatchItem,
  type AuthBatchPhoneInput as TypedAuthBatchPhoneInput,
  type AuthBatchRead as TypedAuthBatch,
  type AuthBatchSnapshot as TypedAuthBatchSnapshot,
  type AuthBatchValidate as TypedAuthBatchValidation,
} from '@stylisttg/api-client'

import { dashboardApiClient } from '@/lib/apiClient'

export type AuthBatchPhoneInput = TypedAuthBatchPhoneInput

export type AuthBatch = TypedAuthBatch

export type AuthBatchItem = TypedAuthBatchItem

export type AuthBatchSnapshot = TypedAuthBatchSnapshot

export type AuthBatchValidation = TypedAuthBatchValidation

const authBatchClient = dashboardApiClient

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
  return validation?.valid_items.map((item) => formatBulkPhoneLine(item.phone_number, item.label ?? null)) ?? []
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
  return validateTypedAuthBatchPhones(authBatchClient, items)
}

export async function createAuthBatch(payload: {
  idempotency_key: string
  label?: string | null
  items: AuthBatchPhoneInput[]
  max_running_commands: number
  max_waiting_input: number
  max_total_active: number
}): Promise<AuthBatchSnapshot> {
  return createTypedAuthBatch(authBatchClient, payload)
}

export async function startAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return startTypedAuthBatch(authBatchClient, batchId)
}

export async function fetchAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return fetchTypedAuthBatch(authBatchClient, batchId)
}

export async function pauseAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return pauseTypedAuthBatch(authBatchClient, batchId)
}

export async function resumeAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return resumeTypedAuthBatch(authBatchClient, batchId)
}

export async function cancelAuthBatch(batchId: string): Promise<AuthBatchSnapshot> {
  return cancelTypedAuthBatch(authBatchClient, batchId)
}

export async function pollAuthBatch(batchId: string, updatedSince?: string | null): Promise<AuthBatchSnapshot> {
  return pollTypedAuthBatch(authBatchClient, batchId, updatedSince ?? undefined)
}

export async function submitAuthBatchCode(batchId: string, itemId: string, code: string): Promise<AuthBatchItem> {
  return submitTypedAuthBatchCode(authBatchClient, batchId, itemId, code)
}

export async function submitAuthBatchPassword(batchId: string, itemId: string, password: string): Promise<AuthBatchItem> {
  return submitTypedAuthBatchPassword(authBatchClient, batchId, itemId, password)
}

export async function retryAuthBatchItem(batchId: string, itemId: string): Promise<AuthBatchItem> {
  return retryTypedAuthBatchItem(authBatchClient, batchId, itemId)
}
